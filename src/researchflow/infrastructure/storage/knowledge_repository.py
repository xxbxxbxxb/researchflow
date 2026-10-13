from dataclasses import replace

from sqlalchemy import select,func
from sqlalchemy.ext.asyncio import AsyncSession

from researchflow.domain.claims import Verification,Claim
from researchflow.domain.errors import ProjectBoundaryError
from researchflow.domain.knowledge import KnowledgeEntry,FollowUpDraft
from researchflow.domain.reports import ResearchResult
from researchflow.infrastructure.storage.codec import decode_dataclass,jsonable
from researchflow.infrastructure.storage.database import Database
from researchflow.infrastructure.storage.models import VerificationRow,ClaimRow,ReportRow,KnowledgeRow,FollowUpRow,TaskRow
from researchflow.infrastructure.storage.repositories import ResearchRepository
from researchflow.ports.repositories import VerificationContext


class KnowledgeRepository:
    def __init__(self, database: Database, research: ResearchRepository | None = None) -> None:
        self.database,self.research = database,research or ResearchRepository(database)

    async def context_in(self, session: AsyncSession, project_id: str, verification_id: str, lock: bool = False) -> VerificationContext:
        row = await session.get(VerificationRow,(project_id,verification_id))
        if row is None:
            raise ProjectBoundaryError('verification not found in project')
        query = select(ClaimRow).where(ClaimRow.project_id==project_id,ClaimRow.claim_id==row.claim_id)
        claim_row = (await session.scalars(query.with_for_update() if lock else query)).one()
        verification = decode_dataclass(Verification,row.data)
        claim = decode_dataclass(Claim,claim_row.data)
        successor = await session.scalar(select(VerificationRow.verification_id).where(VerificationRow.project_id==project_id,VerificationRow.data['supersedes_id'].as_string()==verification_id).limit(1))
        reports = (await session.scalars(select(ReportRow).where(ReportRow.project_id==project_id,ReportRow.task_id==claim.task_id).order_by(ReportRow.version.desc()))).all()
        for report in reports:
            if any(v['verification_id']==verification_id for v in report.data['verifications']):
                return VerificationContext(verification,claim,decode_dataclass(ResearchResult,report.data),successor is None)
        raise ValueError('verification has no immutable report provenance')

    async def verification_context(self, project_id: str, verification_id: str) -> VerificationContext:
        async with self.database.session() as session:
            return await self.context_in(session,project_id,verification_id)

    def entry(self, row: KnowledgeRow) -> KnowledgeEntry:
        return replace(decode_dataclass(KnowledgeEntry,row.data),status=row.status)

    async def get_entry(self, project_id: str, knowledge_id: str) -> KnowledgeEntry | None:
        async with self.database.session() as session:
            row = await session.get(KnowledgeRow,(project_id,knowledge_id))
            return self.entry(row) if row else None

    async def list_entries(self, project_id: str) -> tuple[KnowledgeEntry,...]:
        async with self.database.session() as session:
            rows = (await session.scalars(select(KnowledgeRow).where(KnowledgeRow.project_id==project_id).order_by(KnowledgeRow.knowledge_id))).all()
            return tuple(self.entry(row) for row in rows)

    async def insert_entry(self, session: AsyncSession, entry: KnowledgeEntry) -> KnowledgeEntry:
        existing = await session.get(KnowledgeRow,(entry.project_id,entry.knowledge_id))
        if existing:
            if (existing.verification_id,existing.report_id,existing.supersedes_id)!=(entry.verification_id,entry.report_id,entry.supersedes_id):
                raise ValueError('knowledge identity conflicts with provenance')
            return self.entry(existing)
        session.add(KnowledgeRow(project_id=entry.project_id,knowledge_id=entry.knowledge_id,verification_id=entry.verification_id,report_id=entry.report_id,status=entry.status,supersedes_id=entry.supersedes_id,data=jsonable(entry)))
        await session.flush()
        return entry

    async def accept_entry(self, entry: KnowledgeEntry) -> KnowledgeEntry:
        async with self.database.session.begin() as session:
            context = await self.context_in(session,entry.project_id,entry.verification_id,lock=True)
            if not context.is_current or context.verification.status!='supported':
                raise ValueError('accept requires current supported verification')
            if context.result.report.report_id!=entry.report_id:
                raise ValueError('knowledge provenance does not match report')
            return await self.insert_entry(session,entry)

    async def replace_entry(self, old_id: str, entry: KnowledgeEntry) -> KnowledgeEntry:
        async with self.database.session.begin() as session:
            old = (await session.scalars(select(KnowledgeRow).where(KnowledgeRow.project_id==entry.project_id,KnowledgeRow.knowledge_id==old_id).with_for_update())).one_or_none()
            if old is None or old.verification_id==entry.verification_id:
                raise ValueError('replacement requires a different verification and existing knowledge')
            existing = await session.get(KnowledgeRow,(entry.project_id,entry.knowledge_id))
            if existing:
                return self.entry(existing)
            if old.status!='active' or entry.supersedes_id!=old_id:
                raise ValueError('knowledge already superseded or lineage mismatch')
            context = await self.context_in(session,entry.project_id,entry.verification_id,lock=True)
            if not context.is_current or context.verification.status not in {'supported','contradicted'}:
                raise ValueError('replacement requires a current verification')
            if context.result.report.report_id!=entry.report_id:
                raise ValueError('replacement provenance mismatch')
            new = await self.insert_entry(session,entry)
            old.status = 'superseded'
            return new

    async def save_override(self, project_id: str, old_id: str, verification: Verification, result: ResearchResult) -> Verification:
        async with self.database.session.begin() as session:
            old = await self.context_in(session,project_id,old_id,lock=True)
            if not old.is_current or verification.claim_id!=old.claim.claim_id or verification.supersedes_id!=old_id or not verification.actor:
                raise ValueError('override requires the current verification and actor lineage')
            if (result.project_id,result.task_id,result.run_id)!=(project_id,old.result.task_id,old.result.run_id):
                raise ProjectBoundaryError('override report does not belong to original task/run')
            await self.research.write_verifications(session,project_id,(verification,))
            await self.research.write_result(session,result)
            return verification

    async def save_draft(self, draft: FollowUpDraft) -> FollowUpDraft:
        async with self.database.session.begin() as session:
            parent = await session.get(TaskRow,(draft.project_id,draft.parent_task_id))
            if parent is None:
                raise ProjectBoundaryError('parent task does not belong to project')
            for claim_id in draft.claim_ids:
                claim = await session.get(ClaimRow,(draft.project_id,claim_id))
                if claim is None or claim.task_id!=draft.parent_task_id:
                    raise ProjectBoundaryError('draft claim does not belong to parent task/project')
            old = await session.get(FollowUpRow,(draft.project_id,draft.draft_id))
            if old:
                existing = decode_dataclass(FollowUpDraft,old.data)
                if replace(existing,started_run_id=None)!=replace(draft,started_run_id=None):
                    raise ValueError('draft identity conflict')
                return existing
            session.add(FollowUpRow(project_id=draft.project_id,draft_id=draft.draft_id,parent_task_id=draft.parent_task_id,started_run_id=draft.started_run_id,data=jsonable(draft)))
            return draft

    async def list_drafts(self, project_id: str) -> tuple[FollowUpDraft,...]:
        async with self.database.session() as session:
            rows = (await session.scalars(select(FollowUpRow).where(FollowUpRow.project_id==project_id))).all()
            return tuple(decode_dataclass(FollowUpDraft,row.data) for row in rows)

    async def candidates(self, project_id: str, knowledge_id: str) -> tuple[Verification,...]:
        # Exact wording proposes review; it never changes accepted knowledge.
        async with self.database.session() as session:
            entry = await session.get(KnowledgeRow,(project_id,knowledge_id))
            if entry is None:
                raise ProjectBoundaryError('knowledge is not in this project')
            old = await self.context_in(session,project_id,entry.verification_id)
            rows = (await session.scalars(select(VerificationRow).join(ClaimRow,(ClaimRow.project_id==VerificationRow.project_id)&(ClaimRow.claim_id==VerificationRow.claim_id)).where(VerificationRow.project_id==project_id,VerificationRow.status=='contradicted',VerificationRow.verification_id!=entry.verification_id,func.lower(ClaimRow.data['text'].as_string())==old.claim.text.lower()))).all()
            result = []
            for row in rows:
                candidate = decode_dataclass(Verification,row.data)
                if candidate.verified_at>old.verification.verified_at and (await self.context_in(session,project_id,candidate.verification_id)).is_current:
                    result.append(candidate)
            return tuple(result)
