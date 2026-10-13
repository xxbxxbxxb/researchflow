from dataclasses import replace
from datetime import datetime,timezone
from uuid import uuid4

from researchflow.application.evidence import digest
from researchflow.application.reports import ReportBuilder
from researchflow.domain.claims import Verification,VerificationStatus
from researchflow.domain.knowledge import KnowledgeEntry,FollowUpDraft
from researchflow.domain.projects import TaskRecord
from researchflow.domain.reports import ReportInputs
from researchflow.ports.repositories import KnowledgePort


class KnowledgeService:
    def __init__(self, repository: KnowledgePort) -> None:
        self.repository = repository

    async def accept(self, project_id: str, verification_id: str, actor: str) -> KnowledgeEntry:
        if not actor.strip():
            raise ValueError('review actor is required')
        context = await self.repository.verification_context(project_id,verification_id)
        if not context.is_current or context.verification.status != 'supported':
            raise ValueError('accept requires a current supported verification')
        entry = KnowledgeEntry(digest(f'{project_id}\0accept\0{verification_id}')[:32],project_id,verification_id,context.result.report.report_id,actor,datetime.now(timezone.utc))
        return await self.repository.accept_entry(entry)

    async def override(self, project_id: str, verification_id: str, status: VerificationStatus, reason: str, actor: str) -> Verification:
        if not reason.strip() or not actor.strip():
            raise ValueError('manual override requires a reason and actor')
        context = await self.repository.verification_context(project_id,verification_id)
        if not context.is_current:
            raise ValueError('manual override requires the current verification')
        evidence_ids = context.verification.accepted_evidence_ids or context.claim.proposed_evidence_ids
        verification = Verification(uuid4().hex,context.claim.claim_id,status,evidence_ids,reason.strip(),(*context.verification.checks,'human_override'),'human-review-v1',(('origin','human_override'),),datetime.now(timezone.utc),verification_id,actor)
        old = context.result
        verifications = tuple(verification if item.claim_id==verification.claim_id else item for item in old.verifications)
        unresolved = tuple(c.text for c,v in zip(old.claims,verifications,strict=True) if v.status!='supported')
        inputs = ReportInputs(old.project_id,old.task_id,old.run_id,old.claims,verifications,old.evidences,unresolved,'人工审阅后的报告',old.execution_mode,old.report.retrieval_mode)
        revised = replace(old,report=ReportBuilder().build(inputs),verifications=verifications,unresolved_questions=unresolved)
        return await self.repository.save_override(project_id,verification_id,verification,revised)

    async def supersede(self, project_id: str, old_id: str, new_verification_id: str, actor: str) -> KnowledgeEntry:
        old = await self.repository.get_entry(project_id,old_id)
        if old is None or not actor.strip():
            raise ValueError('knowledge entry or review actor is missing')
        context = await self.repository.verification_context(project_id,new_verification_id)
        if not context.is_current or context.verification.status not in {'supported','contradicted'}:
            raise ValueError('replacement requires a current supported or contradicted verification')
        identity = digest(f'{project_id}\0supersede\0{old_id}\0{new_verification_id}')[:32]
        entry = KnowledgeEntry(identity,project_id,new_verification_id,context.result.report.report_id,actor,datetime.now(timezone.utc),'active',old_id)
        return await self.repository.replace_entry(old_id,entry)

    async def draft_follow_up(self, project_id: str, parent_task_id: str, question: str, claim_ids: tuple[str,...]) -> FollowUpDraft:
        TaskRecord('draft',project_id,question,(),parent_task_id)
        return await self.repository.save_draft(FollowUpDraft(uuid4().hex,project_id,parent_task_id,question,tuple(dict.fromkeys(claim_ids))))
