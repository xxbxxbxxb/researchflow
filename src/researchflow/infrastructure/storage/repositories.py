from dataclasses import replace
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from researchflow.application.evidence import validate_anchor
from researchflow.domain.claims import Claim, Verification
from researchflow.domain.errors import EvidenceConflict, ProjectBoundaryError
from researchflow.domain.projects import Project, TaskRecord
from researchflow.domain.reports import ReportVersion, ResearchResult
from researchflow.domain.sources import AnchoredEvidence, SourceSnapshot, SnapshotPage
from researchflow.infrastructure.storage.codec import decode_dataclass, jsonable
from researchflow.infrastructure.storage.database import Database
from researchflow.infrastructure.storage.models import ClaimRow, DocumentRow, EvidenceRow, LinkRow, PageRow, ProjectRow, ReportRow, SnapshotRow, TaskRow, VerificationRow


class ResearchRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def create_project(self, project: Project) -> Project:
        async with self.database.session() as session,session.begin():
            row = await session.get(ProjectRow,project.project_id)
            if row:
                if (row.name,row.background) != (project.name,project.background):
                    raise ValueError('project identity already exists')
            else:
                session.add(ProjectRow(project_id=project.project_id,name=project.name,background=project.background))
        return project

    async def list_projects(self) -> tuple[Project,...]:
        async with self.database.session() as session:
            rows = (await session.scalars(select(ProjectRow).order_by(ProjectRow.name))).all()
            return tuple(Project(r.project_id,r.name,r.background) for r in rows)

    async def get_project(self, project_id: str) -> Project | None:
        async with self.database.session() as session:
            row = await session.get(ProjectRow,project_id)
            return Project(row.project_id,row.name,row.background) if row else None

    async def save_task(self, task: TaskRecord) -> None:
        async with self.database.session() as session,session.begin():
            if not await session.get(ProjectRow,task.project_id):
                raise ProjectBoundaryError('project does not exist')
            for sid in task.source_ids:
                if not await session.get(SnapshotRow,(task.project_id,sid)):
                    raise ProjectBoundaryError('task source belongs to another project or is missing')
            existing = await session.get(TaskRow,(task.project_id,task.task_id))
            if existing:
                if (existing.question,tuple(existing.source_ids),existing.parent_task_id) != (task.question,task.source_ids,task.parent_task_id):
                    raise ValueError('task input is immutable; create a new task')
                return
            session.add(TaskRow(project_id=task.project_id,task_id=task.task_id,question=task.question,source_ids=list(task.source_ids),parent_task_id=task.parent_task_id))

    async def get_task(self, project_id: str, task_id: str) -> TaskRecord | None:
        async with self.database.session() as session:
            row = await session.get(TaskRow,(project_id,task_id))
            return TaskRecord(row.task_id,row.project_id,row.question,tuple(row.source_ids),row.parent_task_id) if row else None

    async def find_task(self, task_id: str) -> TaskRecord | None:
        async with self.database.session() as session:
            rows = (await session.scalars(select(TaskRow).where(TaskRow.task_id==task_id))).all()
            if len(rows) > 1:
                raise ValueError('task identity is ambiguous without project scope')
            row = rows[0] if rows else None
            return TaskRecord(row.task_id,row.project_id,row.question,tuple(row.source_ids),row.parent_task_id) if row else None

    async def list_tasks(self, project_id: str) -> tuple[TaskRecord,...]:
        async with self.database.session() as session:
            rows = (await session.scalars(select(TaskRow).where(TaskRow.project_id==project_id))).all()
            return tuple(TaskRecord(r.task_id,r.project_id,r.question,tuple(r.source_ids),r.parent_task_id) for r in rows)

    async def snapshot_in(self, session: AsyncSession, project_id: str, snapshot_id: str) -> SourceSnapshot | None:
        row = await session.get(SnapshotRow,(project_id,snapshot_id))
        if row is None:
            return None
        pages = (await session.scalars(select(PageRow).where(PageRow.project_id==project_id,PageRow.snapshot_id==snapshot_id).order_by(PageRow.number))).all()
        return SourceSnapshot(row.snapshot_id,row.project_id,row.source_uri,row.content_hash,tuple(SnapshotPage(p.number,p.text) for p in pages),row.parser_version,row.fetched_at)

    async def get_snapshot(self, project_id: str, snapshot_id: str) -> SourceSnapshot | None:
        async with self.database.session() as session:
            return await self.snapshot_in(session,project_id,snapshot_id)

    async def list_snapshots(self, project_id: str) -> tuple[SourceSnapshot,...]:
        async with self.database.session() as session:
            ids = (await session.scalars(select(SnapshotRow.snapshot_id).where(SnapshotRow.project_id==project_id).order_by(SnapshotRow.fetched_at.desc()))).all()
            items = [await self.snapshot_in(session,project_id,sid) for sid in ids]
            return tuple(item for item in items if item is not None)

    async def write_snapshot(self, session: AsyncSession, snapshot: SourceSnapshot, title: str | None = None) -> SourceSnapshot:
        statement = insert(SnapshotRow).values(project_id=snapshot.project_id,snapshot_id=snapshot.snapshot_id,source_uri=snapshot.source_uri,content_hash=snapshot.content_hash,parser_version=snapshot.parser_version,fetched_at=snapshot.fetched_at).on_conflict_do_nothing().returning(SnapshotRow.snapshot_id)
        added = (await session.execute(statement)).scalar_one_or_none()
        if added is not None:
            for page in snapshot.pages:
                session.add(PageRow(project_id=snapshot.project_id,snapshot_id=snapshot.snapshot_id,number=page.number,text=page.text))
            session.add(DocumentRow(project_id=snapshot.project_id,document_id=snapshot.snapshot_id,snapshot_id=snapshot.snapshot_id,title=title or snapshot.source_uri))
            await session.flush()
            return snapshot
        previous = await self.snapshot_in(session,snapshot.project_id,snapshot.snapshot_id)
        if previous is None or replace(previous,fetched_at=snapshot.fetched_at) != snapshot:
            raise EvidenceConflict('snapshot identity has conflicting source content')
        return previous

    async def save_snapshot(self, snapshot: SourceSnapshot, title: str | None = None) -> SourceSnapshot:
        async with self.database.session() as session,session.begin():
            return await self.write_snapshot(session,snapshot,title)

    async def write_evidences(self, session: AsyncSession, project_id: str, items: tuple[AnchoredEvidence,...]) -> tuple[AnchoredEvidence,...]:
        for item in items:
            if item.project_id != project_id:
                raise ProjectBoundaryError('evidence crosses project scope')
            snapshot = await self.snapshot_in(session,project_id,item.anchor.snapshot_id)
            if snapshot is None:
                raise ValueError('saved snapshot is missing')
            validate_anchor(item,snapshot)
            values = {'project_id':project_id,'evidence_id':item.evidence.evidence_id,'snapshot_id':item.anchor.snapshot_id,'page':item.anchor.page,'data':jsonable(item)}
            added = (await session.execute(insert(EvidenceRow).values(**values).on_conflict_do_nothing().returning(EvidenceRow.evidence_id))).scalar_one_or_none()
            if added is None:
                old = await session.get(EvidenceRow,(project_id,item.evidence.evidence_id))
                if old is None or old.data != values['data']:
                    raise EvidenceConflict('evidence identity has conflicting immutable content')
        return items

    async def add_evidence_batch(self, project_id: str, items: tuple[AnchoredEvidence,...]) -> tuple[AnchoredEvidence,...]:
        async with self.database.session() as session,session.begin():
            return await self.write_evidences(session,project_id,items)

    async def get_evidence(self, project_id: str, evidence_id: str) -> AnchoredEvidence | None:
        async with self.database.session() as session:
            row = await session.get(EvidenceRow,(project_id,evidence_id))
            return decode_dataclass(AnchoredEvidence,row.data) if row else None

    async def immutable(self, session: AsyncSession, model: Any, key_name: str, key: str, project_id: str, values: dict[str,Any]) -> None:
        added = (await session.execute(insert(model).values(**values).on_conflict_do_nothing().returning(getattr(model,key_name)))).scalar_one_or_none()
        if added is None:
            old = await session.get(model,(project_id,key))
            if old is None or old.data != values['data']:
                raise EvidenceConflict('immutable research record conflicts with existing identity')

    async def write_claims(self, session: AsyncSession, project_id: str, claims: tuple[Claim,...]) -> None:
        for claim in claims:
            if claim.project_id != project_id:
                raise ProjectBoundaryError('claim crosses project scope')
            await self.immutable(session,ClaimRow,'claim_id',claim.claim_id,project_id,{'project_id':project_id,'claim_id':claim.claim_id,'task_id':claim.task_id,'data':jsonable(claim)})
            for ref in claim.proposed_evidence_ids:
                await session.execute(insert(LinkRow).values(project_id=project_id,claim_id=claim.claim_id,evidence_id=ref,relationship='proposed').on_conflict_do_nothing())

    async def write_verifications(self, session: AsyncSession, project_id: str, verifications: tuple[Verification,...]) -> None:
        for item in verifications:
            await self.immutable(session,VerificationRow,'verification_id',item.verification_id,project_id,{'project_id':project_id,'verification_id':item.verification_id,'claim_id':item.claim_id,'status':item.status,'data':jsonable(item)})
            for ref in item.accepted_evidence_ids:
                await session.execute(insert(LinkRow).values(project_id=project_id,claim_id=item.claim_id,evidence_id=ref,relationship='accepted').on_conflict_do_nothing())

    async def write_result(self, session: AsyncSession, result: ResearchResult) -> ResearchResult:
        report = result.report
        if (report.project_id,report.task_id,report.run_id) != (result.project_id,result.task_id,result.run_id):
            raise ValueError('report does not belong to this result')
        task = (await session.scalars(select(TaskRow).where(TaskRow.project_id==result.project_id,TaskRow.task_id==result.task_id).with_for_update())).one_or_none()
        if task is None:
            raise ValueError('task does not exist in project')
        old = await session.get(ReportRow,(result.project_id,report.report_id))
        if old:
            existing = decode_dataclass(ResearchResult,old.data)
            if replace(existing,report=replace(existing.report,version=report.version)) != result:
                raise EvidenceConflict('report identity has conflicting content')
            return existing
        await self.write_evidences(session,result.project_id,result.evidences)
        await self.write_claims(session,result.project_id,result.claims)
        await self.write_verifications(session,result.project_id,result.verifications)
        maximum = await session.scalar(select(func.max(ReportRow.version)).where(ReportRow.project_id==result.project_id,ReportRow.task_id==result.task_id))
        stored = replace(result,report=replace(report,version=(maximum or 0)+1))
        session.add(ReportRow(project_id=result.project_id,report_id=report.report_id,task_id=result.task_id,run_id=result.run_id,version=stored.report.version,data=jsonable(stored),created_at=report.created_at))
        await session.flush()
        return stored

    async def save_result(self, result: ResearchResult) -> None:
        async with self.database.session() as session,session.begin():
            await self.write_result(session,result)

    async def get_result(self, project_id: str, report_id: str) -> ResearchResult:
        async with self.database.session() as session:
            row = await session.get(ReportRow,(project_id,report_id))
            if row is None:
                raise ValueError('report not found in project')
            return decode_dataclass(ResearchResult,row.data)

    async def get_report(self, project_id: str, report_id: str) -> ReportVersion:
        return (await self.get_result(project_id,report_id)).report

    async def list_reports(self, project_id: str, task_id: str | None = None) -> tuple[ReportVersion,...]:
        async with self.database.session() as session:
            query = select(ReportRow).where(ReportRow.project_id==project_id)
            if task_id:
                query = query.where(ReportRow.task_id==task_id)
            rows = (await session.scalars(query.order_by(ReportRow.created_at.desc()))).all()
            return tuple(decode_dataclass(ResearchResult,row.data).report for row in rows)
