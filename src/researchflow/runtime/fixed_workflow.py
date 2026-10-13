from dataclasses import asdict
from typing import Literal, cast

from researchflow.application.claims import ClaimExtractor
from researchflow.application.reports import ReportBuilder
from researchflow.application.retrieval import EvidenceSelector
from researchflow.application.verification import ClaimVerifier
from researchflow.domain.reports import ReportInputs, ResearchResult
from researchflow.domain.runs import RunHandle, RunOutcome, StepOutput
from researchflow.ports.model import ChatModelPort
from researchflow.ports.repositories import ResearchReadRepository
from researchflow.ports.retrieval import RetrievalCandidate, RetrievalResult, Retriever
from researchflow.ports.runtime import InputVersionMismatchError, RunRepositoryPort
from researchflow.ports.telemetry import NullTrace

PHASES = ('collect','retrieve','evidence','claims','verify','report')
WORKFLOW_VERSION = 'fixed-v1'


class FixedWorkflow:
    def __init__(self, runs: RunRepositoryPort, research: ResearchReadRepository, retriever: Retriever, model: ChatModelPort, execution_mode: Literal['demo','live'] = 'live', collector=None,trace=None) -> None:
        self.runs,self.research,self.retriever,self.model,self.execution_mode = runs,research,retriever,model,execution_mode
        self.collector=collector
        self.trace=trace or NullTrace()

    workflow_version=WORKFLOW_VERSION

    async def inputs(self, handle: RunHandle):
        record = await self.runs.get_run(handle.project_id,handle.run_id)
        task = await self.research.get_task(handle.project_id,handle.task_id)
        if record is None or task is None:
            raise ValueError('run/task input is missing')
        if record.input_manifest['workflow_version'] != self.workflow_version or record.input_manifest['execution_mode'] != self.execution_mode:
            raise InputVersionMismatchError('run input policy is incompatible with this driver')
        return record,task

    async def step(self,handle: RunHandle,phase: str):
        with self.trace.span('phase',{'run_id':handle.run_id,'task_id':handle.task_id,'project_id':handle.project_id,'step_id':phase,'epoch':handle.epoch}):
            return await self._step(handle,phase)

    async def _step(self,handle: RunHandle,phase: str):
        record,task=await self.inputs(handle)
        receipt=await self.runs.get_receipt(handle,phase)
        if receipt:
            return receipt.output
        outputs={}
        for previous in PHASES[:PHASES.index(phase)]:
            saved=await self.runs.get_receipt(handle,previous)
            if saved is None:
                raise ValueError("prior business phase has no commit receipt")
            outputs[previous]=saved.output
        if phase == 'collect':
            collect_ids=list(record.input_manifest['source_ids'])
            if self.collector is not None and record.input_manifest.get('collect_sources'):
                collected=await self.collector.collect(handle,task.question)
                collect_ids.extend(collected.source_ids)
            output = StepOutput(data={'source_ids':list(dict.fromkeys(collect_ids))})
        elif phase == 'retrieve':
            source_ids = tuple(outputs['collect'].data['source_ids'])
            result = await self.retriever.search(handle.project_id,task.question,source_ids) if source_ids else RetrievalResult((),'lexical',None)
            output = StepOutput(data=asdict(result))
        elif phase == 'evidence':
            found = outputs['retrieve'].data
            result = RetrievalResult(tuple(RetrievalCandidate(**c) for c in found['candidates']),found['mode'],found['embedding_version'])
            output = StepOutput(evidences=EvidenceSelector().select(result))
        elif phase == 'claims':
            claims = await ClaimExtractor(self.model,max_claims=4).extract(task,outputs['evidence'].evidences)
            output = StepOutput(claims=claims)
        elif phase == 'verify':
            snapshots = []
            for sid in outputs['collect'].data['source_ids']:
                snapshot = await self.research.get_snapshot(handle.project_id,sid)
                if snapshot is None:
                    raise ValueError('immutable run source is missing')
                snapshots.append(snapshot)
            verifications = await ClaimVerifier(self.model).verify(outputs['claims'].claims,outputs['evidence'].evidences,tuple(snapshots))
            output = StepOutput(verifications=verifications)
        else:
            claims,verifications,evidences = outputs['claims'].claims,outputs['verify'].verifications,outputs['evidence'].evidences
            unresolved = tuple(c.text for c,v in zip(claims,verifications,strict=True) if v.status != 'supported')
            if not claims:
                unresolved = ('请补充能够回答研究问题的原始资料。',)
            mode = cast(Literal['lexical','hybrid'],outputs['retrieve'].data['mode'])
            inputs = ReportInputs(handle.project_id,handle.task_id,handle.run_id,claims,verifications,evidences,unresolved,task.question,self.execution_mode,mode)
            report = ReportBuilder().build(inputs)
            research_result = ResearchResult(handle.project_id,handle.task_id,handle.run_id,report,claims,verifications,evidences,unresolved,self.execution_mode)
            output = StepOutput(result=research_result)
        return (await self.runs.commit_step(handle,phase,output)).output

    async def execute(self,handle: RunHandle) -> RunOutcome:
        record,_=await self.inputs(handle)
        for phase in PHASES:
            output=await self.step(handle,phase)
        assert output.result is not None
        state: Literal['awaiting_review','succeeded']='awaiting_review' if record.input_manifest.get('require_review',False) else 'succeeded'
        return RunOutcome(state,output.result.report.report_id)
