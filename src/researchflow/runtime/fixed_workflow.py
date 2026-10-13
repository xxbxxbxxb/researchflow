from dataclasses import asdict
from typing import Literal, cast

from researchflow.application.claims import ClaimExtractor
from researchflow.application.verification import ClaimVerifier
from researchflow.application.reports import ReportBuilder
from researchflow.application.retrieval import EvidenceSelector
from researchflow.domain.reports import ReportInputs, ResearchResult
from researchflow.domain.runs import RunHandle, RunOutcome, StepOutput
from researchflow.ports.model import ChatModelPort
from researchflow.ports.repositories import ResearchReadRepository
from researchflow.ports.retrieval import Retriever, RetrievalResult, RetrievalCandidate
from researchflow.ports.runtime import RunRepositoryPort, InputVersionMismatchError

PHASES = ('collect','retrieve','evidence','claims','verify','report')
WORKFLOW_VERSION = 'fixed-v1'


class FixedWorkflow:
    def __init__(self, runs: RunRepositoryPort, research: ResearchReadRepository, retriever: Retriever, model: ChatModelPort, execution_mode: Literal['demo','live'] = 'live') -> None:
        self.runs,self.research,self.retriever,self.model,self.execution_mode = runs,research,retriever,model,execution_mode

    async def execute(self, handle: RunHandle) -> RunOutcome:
        record = await self.runs.get_run(handle.project_id,handle.run_id)
        task = await self.research.get_task(handle.project_id,handle.task_id)
        if record is None or task is None:
            raise ValueError('run/task input is missing')
        if record.input_manifest['workflow_version'] != WORKFLOW_VERSION or record.input_manifest['execution_mode'] != self.execution_mode:
            raise InputVersionMismatchError('run input policy is incompatible with this driver')
        outputs = {}
        for phase in PHASES:
            receipt = await self.runs.get_receipt(handle,phase)
            if receipt:
                outputs[phase] = receipt.output
                continue
            if phase == 'collect':
                output = StepOutput(data={'source_ids':record.input_manifest['source_ids']})
            elif phase == 'retrieve':
                source_ids = tuple(outputs['collect'].data['source_ids'])
                result = await self.retriever.search(handle.project_id,task.question,source_ids) if source_ids else RetrievalResult((),'lexical',None)
                output = StepOutput(data=asdict(result))
            elif phase == 'evidence':
                found = outputs['retrieve'].data
                result = RetrievalResult(tuple(RetrievalCandidate(**c) for c in found['candidates']),found['mode'],found['embedding_version'])
                output = StepOutput(evidences=EvidenceSelector().select(result))
            elif phase == 'claims':
                claims = await ClaimExtractor(self.model).extract(task,outputs['evidence'].evidences)
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
                result = ResearchResult(handle.project_id,handle.task_id,handle.run_id,report,claims,verifications,evidences,unresolved,self.execution_mode)
                output = StepOutput(result=result)
            outputs[phase] = (await self.runs.commit_step(handle,phase,output)).output
        assert outputs['report'].result is not None
        return RunOutcome('succeeded',outputs['report'].result.report.report_id)
