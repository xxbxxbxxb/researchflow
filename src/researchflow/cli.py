import argparse
import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx

from researchflow.application.evidence import manual_evidence
from researchflow.application.research import ResearchService
from researchflow.domain.projects import TaskRecord
from researchflow.domain.research import Evidence
from researchflow.infrastructure.llm.chat_model import OpenAIChatModel
from researchflow.infrastructure.llm.demo_model import CASES, DemoCaseModel
from researchflow.infrastructure.llm.openai_compatible import OpenAICompatibleConfig
from researchflow.infrastructure.storage.codec import jsonable


async def run(args):
    if args.command == 'hash-password':
        from getpass import getpass
        from argon2 import PasswordHasher
        password = await asyncio.to_thread(getpass,'New ResearchFlow password: ')
        if len(password)<12:
            raise ValueError('Use a password with at least 12 characters.')
        return {'password_hash':await asyncio.to_thread(PasswordHasher().hash,password)},0
    if args.command == 'serve':
        import uvicorn
        from researchflow.settings import Settings
        from researchflow.api.app import create_app
        settings = Settings.from_env()
        settings.validate_binding(args.host)
        await uvicorn.Server(uvicorn.Config(create_app(settings),host=args.host,port=args.port,proxy_headers=False)).serve()
        return {'stopped':True},0
    if args.command == 'worker':
        from researchflow.composition import worker_resources
        async with worker_resources(args.mode) as worker:
            if args.once:
                return {'processed':await worker.run_once(),'execution_mode':args.mode},0
            await worker.run_forever()
    if args.command == 'demo':
        case = args.case
        fixture = CASES[case]
        payload = {'question':fixture['question'],'evidence':[{'id':'e1','source':'合成演示资料','locator':'paragraph 1','text':fixture['source']}]} if fixture['source'] else {'question':fixture['question'],'evidence':[]}
        mode = 'demo'
    else:
        mode = args.mode
        if mode == 'live' and not all(os.getenv(k) for k in ('RF_LLM_BASE_URL','RF_LLM_API_KEY','RF_LLM_MODEL')):
            return {'error':{'code':'configuration_missing','message':'Live mode requires RF_LLM_BASE_URL, RF_LLM_API_KEY and RF_LLM_MODEL.'}},1
        payload = json.loads(Path(args.input).read_text(encoding='utf-8'))
        case = payload.get('demo_case','supported')
        if mode == 'demo' and 'demo_case' not in payload:
            return {'error':{'code':'configuration_missing','message':'Demo mode requires an explicit demo_case fixture.'}},1
    task = TaskRecord(payload.get('task_id','demo-task'),payload.get('project_id','demo-project'),payload['question'])
    pairs = [manual_evidence(task.project_id,Evidence(row.get('id',f'e{i+1}'),row.get('source','manual'),row.get('locator','paragraph 1'),row['text'])) for i,row in enumerate(payload.get('evidence',[]))]
    snapshots = tuple(s for s,_ in pairs)
    evidences = tuple(e for _,e in pairs)
    async with httpx.AsyncClient(timeout=60,trust_env=False) as client:
        if mode == 'demo':
            model = DemoCaseModel(case)
        else:
            model = OpenAIChatModel(client,OpenAICompatibleConfig(os.environ['RF_LLM_BASE_URL'],os.environ['RF_LLM_API_KEY'],os.environ['RF_LLM_MODEL']))
        async with asyncio.timeout(300):
            result = await ResearchService(model,mode).run_manual(task,snapshots,evidences,uuid4().hex)
    return result,0


def main() -> int:
    parser = argparse.ArgumentParser(prog='researchflow')
    commands = parser.add_subparsers(dest='command',required=True)
    demo = commands.add_parser('demo',help='Run a clearly marked fixed example')
    demo.add_argument('--case',choices=list(CASES),default='supported')
    demo.add_argument('--format',choices=['json','markdown'],default='markdown')
    research = commands.add_parser('research',help='Run a manual-source research task')
    research.add_argument('--input',required=True)
    research.add_argument('--mode',choices=['live','demo'],default='live')
    research.add_argument('--format',choices=['json','markdown'],default='markdown')
    worker = commands.add_parser('worker',help='Execute durable database runs')
    worker.add_argument('--once',action='store_true')
    worker.add_argument('--mode',choices=['live','demo'],default='live')
    worker.set_defaults(format='json')
    server = commands.add_parser('serve',help='Start the authenticated ResearchFlow API')
    server.add_argument('--host',default='127.0.0.1')
    server.add_argument('--port',type=int,default=8000)
    server.set_defaults(format='json')
    password = commands.add_parser('hash-password',help='Generate an Argon2id hash interactively')
    password.set_defaults(format='json')
    args = parser.parse_args()
    try:
        result,code = asyncio.run(run(args))
    except (ValueError,KeyError,TypeError) as exc:
        result,code = {'error':{'code':'invalid_output','message':str(exc)}},1
    except (OSError,RuntimeError,TimeoutError):
        result,code = {'error':{'code':'operation_failed','message':'Research operation could not be completed.'}},1
    if args.format == 'markdown' and code == 0:
        print(result.report.markdown)
    else:
        print(json.dumps(jsonable(result),ensure_ascii=False))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
