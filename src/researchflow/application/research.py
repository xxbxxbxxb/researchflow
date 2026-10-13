from typing import Literal

from researchflow.application.claims import ClaimExtractor
from researchflow.application.evidence import EvidenceLedger
from researchflow.application.reports import ReportBuilder
from researchflow.application.verification import ClaimVerifier
from researchflow.domain.projects import TaskRecord
from researchflow.domain.reports import ReportInputs, ResearchResult
from researchflow.domain.sources import AnchoredEvidence, SourceSnapshot
from researchflow.ports.model import ChatModelPort


class ResearchService:
    def __init__(self, model: ChatModelPort, execution_mode: Literal['demo','live'] = 'live') -> None:
        self.extractor = ClaimExtractor(model)
        self.verifier = ClaimVerifier(model)
        self.builder = ReportBuilder()
        self.execution_mode = execution_mode

    async def run_manual(self, task: TaskRecord, snapshots: tuple[SourceSnapshot, ...], evidences: tuple[AnchoredEvidence, ...], run_id: str) -> ResearchResult:
        ledger = EvidenceLedger(snapshots)
        ledger.add_batch(task.project_id,evidences)
        claims = await self.extractor.extract(task,evidences)
        verifications = await self.verifier.verify(claims,evidences,snapshots)
        unresolved = tuple(c.text for c,v in zip(claims,verifications,strict=True) if v.status != 'supported')
        if not claims:
            unresolved = ('请补充能够回答研究问题的原始资料。',)
        inputs = ReportInputs(task.project_id,task.task_id,run_id,claims,verifications,evidences,unresolved,task.question,self.execution_mode)
        return ResearchResult(task.project_id,task.task_id,run_id,self.builder.build(inputs),claims,verifications,evidences,unresolved,self.execution_mode)
