import json
import os
from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import httpx

from researchflow.application.evidence import anchor_evidence, digest
from researchflow.application.verification import VERIFIER_VERSION, ClaimVerifier
from researchflow.domain.claims import Claim
from researchflow.domain.runs import RunHandle
from researchflow.domain.sources import SnapshotPage, SourceSnapshot
from researchflow.evaluation.dataset import EvaluationReport, Prediction
from researchflow.evaluation.metrics import compute_metrics
from researchflow.infrastructure.llm.chat_model import OpenAIChatModel
from researchflow.infrastructure.llm.openai_compatible import OpenAICompatibleConfig
from researchflow.ports.model import ChatModelPort, ChatResponse
from researchflow.runtime.budget import MemoryBudgetRepository
from researchflow.runtime.model_runtime import BoundChatModel, ModelRuntime


class EvaluationRunner:
    async def run(self,dataset,mode,output_dir: Path):
        if mode not in ('contract','live'):
            raise ValueError('unknown evaluation mode')
        configured=all(os.getenv(k) for k in ('RF_LLM_BASE_URL','RF_LLM_API_KEY','RF_LLM_MODEL','RF_CONTEXT_WINDOW'))
        metadata={'verifier_version':VERIFIER_VERSION,'material':'full abstract, no gold label/rationale in live prompt','strategy_hash':sha256(Path(__file__).parents[1].joinpath('application/verification.py').read_bytes()).hexdigest(),'created_at':datetime.now(UTC).isoformat(),'input_tokens':None,'output_tokens':None,'estimated_cost':None}
        if mode=='live' and not configured:
            report=EvaluationReport('not_run',mode,False,len(dataset),(),None,{**metadata,'reason':'configuration_missing'})
        else:
            predictions=[]
            attempts=[]
            async with httpx.AsyncClient(timeout=60,trust_env=False) as client:
                for case in dataset:
                    text='\n'.join(case.abstract)
                    snapshot=SourceSnapshot(digest(str(case.doc_id)+text),'evaluation','scifact:doc/'+str(case.doc_id),digest(text),(SnapshotPage(1,text),),'scifact-abstract-v1',datetime.now(UTC))
                    evidence=anchor_evidence(snapshot,1,0,len(text))
                    eid=evidence.evidence.evidence_id
                    claim=Claim(case.case_id,'eval-task','evaluation',case.claim,(eid,))
                    provider: ChatModelPort
                    if mode=='contract':
                        class Fixture:
                            async def complete(self,request):
                                return ChatResponse(json.dumps({'verifications':[{'claim_id':claim.claim_id,'status':case.gold,'evidence_ids':[eid] if case.gold!='insufficient' else [],'rationale':'Seeded contract fixture, not model quality.','quotes':[{'evidence_id':eid,'quote':text}] if case.gold!='insufficient' else []}]}),model='contract:seeded-gold')
                        provider=Fixture()
                    else:
                        provider=OpenAIChatModel(client,OpenAICompatibleConfig(os.environ['RF_LLM_BASE_URL'],os.environ['RF_LLM_API_KEY'],os.environ['RF_LLM_MODEL']))
                    handle=RunHandle(uuid4().hex,'evaluation','eval-task',1,'evaluation')
                    runtime=ModelRuntime(provider,MemoryBudgetRepository(handle),65536 if mode=='contract' else int(os.environ['RF_CONTEXT_WINDOW']))
                    try:
                        verdict=(await ClaimVerifier(BoundChatModel(runtime,handle)).verify((claim,),(evidence,),(snapshot,)))[0]
                        predictions.append(Prediction(case.case_id,case.gold,verdict.status,verdict.accepted_evidence_ids,(eid,)))
                    except Exception as exc:
                        predictions.append(Prediction(case.case_id,case.gold,'failed',(),(eid,),type(exc).__name__))
                    attempts.extend(await runtime.budgets.list_usage(handle.project_id,handle.run_id))
            def total(key):
                return sum(a[key] for a in attempts) if attempts and all(a[key] is not None for a in attempts) else None
            metadata.update(attempts=len(attempts),input_tokens=total('input_tokens'),output_tokens=total('output_tokens'),estimated_cost=total('estimated_cost'))
            report=EvaluationReport('completed',mode,mode=='live',len(dataset),tuple(predictions),compute_metrics(tuple(predictions)),{**metadata,'model':os.getenv('RF_LLM_MODEL') if mode=='live' else 'contract:seeded-gold'})
        output_dir.mkdir(parents=True,exist_ok=True)
        (output_dir/'report.json').write_text(json.dumps(asdict(report),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        errors=[asdict(p) for p in report.predictions if p.predicted!=p.gold]
        (output_dir/'errors.json').write_text(json.dumps(errors,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        return report
