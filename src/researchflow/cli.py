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
    if args.command == 'validate':
        if args.scope=='live':
            from researchflow.evaluation.dataset import load_split
            from researchflow.evaluation.runner import EvaluationRunner
            result=await EvaluationRunner().run(load_split('holdout'),'live',Path(args.output))
            return result,0 if result.status=='completed' else 2
        from researchflow.release import validate
        result=await asyncio.to_thread(validate,Path(args.output))
        return result,0 if result['status']=='passed' else 1 if result['status']=='failed' else 2
    if args.command == 'evaluate':
        from researchflow.evaluation.dataset import load_split, validate_splits
        from researchflow.evaluation.runner import EvaluationRunner
        validate_splits(load_split('development'),load_split('holdout'))
        result=await EvaluationRunner().run(load_split(args.split),args.mode,Path(args.output))
        return result,0 if result.status=='completed' else 2
    if args.command == 'hash-password':
        from getpass import getpass

        from argon2 import PasswordHasher
        password = await asyncio.to_thread(getpass,'New ResearchFlow password: ')
        if len(password)<12:
            raise ValueError('Use a password with at least 12 characters.')
        return {'password_hash':await asyncio.to_thread(PasswordHasher().hash,password)},0
    if args.command == 'serve':
        import uvicorn

        from researchflow.api.app import create_app
        from researchflow.settings import Settings
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
        if mode == 'live' and not all(os.getenv(k) for k in ('RF_LLM_BASE_URL','RF_LLM_API_KEY','RF_LLM_MODEL','RF_CONTEXT_WINDOW')):
            return {'error':{'code':'configuration_missing','message':'Live mode requires provider credentials and RF_CONTEXT_WINDOW.'}},1
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
        from researchflow.domain.runs import RunHandle
        from researchflow.runtime.budget import MemoryBudgetRepository
        from researchflow.runtime.model_runtime import BoundChatModel, ModelRuntime
        handle=RunHandle(uuid4().hex,task.project_id,task.task_id,1,'cli')
        runtime=ModelRuntime(model,MemoryBudgetRepository(handle),context_window=int(os.environ['RF_CONTEXT_WINDOW']) if mode=='live' else 65536)
        async with asyncio.timeout(300):
            await runtime.tick(handle)
            result = await ResearchService(BoundChatModel(runtime,handle),mode).run_manual(task,snapshots,evidences,handle.run_id)
            await runtime.tick(handle)
    return result,0


def main() -> int:
    parser = argparse.ArgumentParser(prog='researchflow')
    commands = parser.add_subparsers(dest='command',required=True)
    validation=commands.add_parser('validate',help='Run engineering or live release validation')
    validation.add_argument('--scope',choices=['engineering','live'],default='engineering')
    validation.add_argument('--output',default='artifacts/verification')
    validation.set_defaults(format='json')
    evaluate=commands.add_parser('evaluate',help='Evaluate evidence support on traceable SciFact labels')
    evaluate.add_argument('--split',choices=['development','holdout'],default='development')
    evaluate.add_argument('--mode',choices=['contract','live'],default='contract')
    evaluate.add_argument('--output',default='artifacts/evaluation')
    evaluate.set_defaults(format='json')
    demo = commands.add_parser('demo',help='Run a clearly marked fixed example')
    demo.add_argument('--case',choices=list(CASES),default='supported')
    demo.add_argument('--format',choices=['json','markdown'],default='markdown')
    research = commands.add_parser('research',help='Run a manual-source research task')
    research.add_argument('--input',required=True)
    research.add_argument('--mode',choices=['live','demo'],default='live')
    research.add_argument('--format',choices=['json','markdown'],default='markdown')
    worker = commands.add_parser('worker',help='Execute durable database runs')
    worker.add_argument('--once',action='store_true')
    worker.add_argument('--mode',choices=['live','demo'],default=os.getenv('RF_MODE','live'))
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
        import sys
        if hasattr(sys.stdout,'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        print(result.report.markdown)
    else:
        print(json.dumps(jsonable(result),ensure_ascii=True))
    return code


if __name__ == '__main__':
    raise SystemExit(main())
