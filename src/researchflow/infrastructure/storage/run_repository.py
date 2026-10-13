import json
from dataclasses import replace
from datetime import timedelta
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from researchflow.application.claims import CLAIM_PROMPT_VERSION
from researchflow.domain.runs import RunHandle, RunRecord, RunState, StepOutput, StepReceipt, LeaseState
from researchflow.domain.errors import ProjectBoundaryError
from researchflow.infrastructure.storage.codec import decode_dataclass, jsonable
from researchflow.infrastructure.storage.database import Database
from researchflow.infrastructure.storage.models import RunRow, StepRow, EventRow, TaskRow, ClaimRow, SnapshotRow, ProjectRow, IdempotencyRow, ReviewRow, BudgetRow, OperationSlotRow
from researchflow.infrastructure.storage.repositories import ResearchRepository
from researchflow.ports.runtime import RunOwnershipLostError, RunCancelledError, InputVersionMismatchError
from researchflow.domain.runs import ReviewDecision
from researchflow.domain.tool_calls import ToolResult
from researchflow.infrastructure.storage.models import ToolRow, FollowUpRow
from researchflow.application.retrieval import chunk_snapshot
from researchflow.infrastructure.storage.models import ChunkRow
from sqlalchemy.dialects.postgresql import insert


class RunRepository:
    def __init__(self, database: Database, research: ResearchRepository | None = None, lease_seconds: float = 5.0) -> None:
        if not 0 < lease_seconds <= 30:
            raise ValueError('invalid lease duration')
        self.database, self.research, self.lease_seconds = database, research or ResearchRepository(database), lease_seconds

    def record(self, row: RunRow) -> RunRecord:
        return RunRecord(row.run_id,row.project_id,row.task_id,cast(RunState,row.state),row.epoch,row.owner_id,row.lease_until,row.cancel_requested,row.input_version,row.input_manifest,row.created_at,row.updated_at,row.error_code)

    async def now(self, session: AsyncSession):
        return await session.scalar(select(func.clock_timestamp()))

    def event(self, session: AsyncSession, row: RunRow, kind: str, now, data: dict[str,Any] | None = None) -> None:
        session.add(EventRow(project_id=row.project_id,run_id=row.run_id,kind=kind,data=data or {},created_at=now))

    async def enqueue(self, task_id: str, project_id: str, input_version: str, input_manifest: dict[str,Any] | None = None) -> RunRecord:
        async with self.database.session.begin() as session:
            return await self.enqueue_in(session,task_id,project_id,input_version,input_manifest)

    async def enqueue_in(self, session: AsyncSession, task_id: str, project_id: str, input_version: str, input_manifest: dict[str,Any] | None = None) -> RunRecord:
        if not input_version.strip():
            raise ValueError('input version is required')
        task = await session.get(TaskRow,(project_id,task_id))
        if task is None:
            raise ProjectBoundaryError('task does not belong to project')
        sources = []
        source_ids = task.source_ids or list((await session.scalars(select(SnapshotRow.snapshot_id).where(SnapshotRow.project_id==project_id).order_by(SnapshotRow.snapshot_id))).all())
        for sid in source_ids:
            snapshot = await self.research.snapshot_in(session,project_id,sid)
            if snapshot is None:
                raise ValueError('saved task source is missing')
            sources.append({'snapshot_id':sid,'content_hash':snapshot.content_hash,'parser_version':snapshot.parser_version})
        manifest = json.loads(json.dumps(input_manifest or {},allow_nan=False))
        manifest.update(sources=sources,question=task.question,source_ids=list(source_ids),parser_versions=sorted({s['parser_version'] for s in sources}))
        manifest.setdefault('workflow_version','fixed-v1')
        manifest.setdefault('prompt_version',CLAIM_PROMPT_VERSION)
        manifest.setdefault('model_version','unconfigured')
        manifest.setdefault('execution_mode','live')
        now = await self.now(session)
        row = RunRow(project_id=project_id,task_id=task_id,run_id=uuid4().hex,state='queued',epoch=0,owner_id=None,lease_until=None,cancel_requested=False,input_version=input_version,input_manifest=manifest,created_at=now,updated_at=now)
        session.add(row)
        await session.flush()
        self.event(session,row,'queued',now)
        return self.record(row)


    async def claim_next(self, owner_id: str) -> RunHandle | None:
        if not owner_id.strip():
            raise ValueError('owner_id is required')
        async with self.database.session.begin() as session:
            row = (await session.scalars(select(RunRow).where(RunRow.state=='queued',RunRow.cancel_requested.is_(False)).order_by(RunRow.created_at,RunRow.run_id).with_for_update(skip_locked=True).limit(1))).one_or_none()
            if row is None:
                return None
            now = await self.now(session)
            row.state,row.owner_id,row.epoch,row.updated_at = 'running',owner_id,row.epoch+1,now
            row.lease_until = now + timedelta(seconds=self.lease_seconds)
            self.event(session,row,'claimed',now,{'epoch':row.epoch})
            return RunHandle(row.run_id,row.project_id,row.task_id,row.epoch,owner_id)

    async def enqueue_idempotent(self, task_id: str, project_id: str, input_version: str, manifest: dict[str,Any], key: str, payload_hash: str) -> RunRecord:
        if not key.strip() or len(key)>200:
            raise ValueError('idempotency key is required and must be at most 200 characters')
        async with self.database.session.begin() as session:
            project = (await session.scalars(select(ProjectRow).where(ProjectRow.project_id==project_id).with_for_update())).one_or_none()
            if project is None:
                raise ProjectBoundaryError('project does not exist')
            old = await session.get(IdempotencyRow,(project_id,key))
            if old:
                if old.payload_hash != payload_hash:
                    raise ValueError('idempotency_conflict')
                row = await session.get(RunRow,(project_id,old.run_id))
                assert row is not None
                return self.record(row)
            record = await self.enqueue_in(session,task_id,project_id,input_version,manifest)
            session.add(IdempotencyRow(project_id=project_id,request_key=key,payload_hash=payload_hash,run_id=record.run_id))
            return record

    async def fence(self, session: AsyncSession, handle: RunHandle, allow_cancel: bool = False) -> RunRow:
        row = (await session.scalars(select(RunRow).where(RunRow.project_id==handle.project_id,RunRow.run_id==handle.run_id).with_for_update())).one_or_none()
        now = await self.now(session)
        if row is None or row.task_id != handle.task_id or row.epoch != handle.epoch or row.owner_id != handle.owner_id or row.state != 'running' or row.lease_until is None or row.lease_until <= now:
            raise RunOwnershipLostError('run lease or ownership no longer valid')
        if row.cancel_requested and not allow_cancel:
            raise RunCancelledError('research cancellation was requested')
        return row

    async def heartbeat(self, handle: RunHandle) -> LeaseState:
        async with self.database.session.begin() as session:
            row = await self.fence(session,handle)
            now = await self.now(session)
            row.lease_until,row.updated_at = now+timedelta(seconds=self.lease_seconds),now
            return LeaseState(handle,row.lease_until)

    async def recover_expired(self, owner_id: str) -> RunHandle | None:
        if not owner_id.strip():
            raise ValueError('owner_id is required')
        async with self.database.session.begin() as session:
            rows = (await session.scalars(select(RunRow).where(
                RunRow.state=='running',RunRow.lease_until <= func.clock_timestamp()
            ).order_by(RunRow.created_at).with_for_update(skip_locked=True).limit(100))).all()
            for row in rows:
                now = await self.now(session)
                budget = await session.get(BudgetRow,(row.project_id,row.run_id))
                if budget is not None and budget.active:
                    # Unknown crash duration is conservatively charged to the old lease.
                    elapsed = max(0.0,(row.lease_until-budget.active_updated_at).total_seconds())
                    budget.active_elapsed_seconds = min(float(budget.limits['active_timeout_seconds']),budget.active_elapsed_seconds+elapsed)
                    budget.active_updated_at,budget.active = now,False
                await session.execute(delete(OperationSlotRow).where(OperationSlotRow.project_id==row.project_id,OperationSlotRow.run_id==row.run_id))
                if row.cancel_requested:
                    row.state,row.owner_id,row.lease_until,row.updated_at = 'cancelled',None,None,now
                    self.event(session,row,'cancelled',now)
                    continue
                row.owner_id,row.epoch,row.updated_at = owner_id,row.epoch+1,now
                row.lease_until = now+timedelta(seconds=self.lease_seconds)
                self.event(session,row,'recovered',now,{'epoch':row.epoch})
                return RunHandle(row.run_id,row.project_id,row.task_id,row.epoch,owner_id)
            return None

    async def get_run(self, project_id: str, run_id: str) -> RunRecord | None:
        async with self.database.session() as session:
            row = await session.get(RunRow,(project_id,run_id))
            return self.record(row) if row else None

    async def list_runs(self, project_id: str, task_id: str | None = None) -> tuple[RunRecord,...]:
        async with self.database.session() as session:
            filters = [RunRow.project_id==project_id]
            if task_id:
                filters.append(RunRow.task_id==task_id)
            rows = (await session.scalars(select(RunRow).where(*filters).order_by(RunRow.created_at.desc()))).all()
            return tuple(self.record(row) for row in rows)

    def receipt(self, row: StepRow) -> StepReceipt:
        return StepReceipt(row.run_id,row.step_key,decode_dataclass(StepOutput,row.output),row.committed_at)

    async def get_receipt(self, handle: RunHandle, step_key: str) -> StepReceipt | None:
        async with self.database.session.begin() as session:
            await self.fence(session,handle)
            row = await session.get(StepRow,(handle.project_id,handle.run_id,step_key))
            return self.receipt(row) if row else None

    async def commit_step(self, handle: RunHandle, step_key: str, output: StepOutput) -> StepReceipt:
        if not step_key.strip() or len(step_key)>200:
            raise ValueError('invalid step key')
        async with self.database.session.begin() as session:
            run = await self.fence(session,handle)
            old = await session.get(StepRow,(handle.project_id,handle.run_id,step_key))
            if old:
                receipt = self.receipt(old)
                comparable = output
                if output.result and receipt.output.result:
                    comparable = replace(output,result=replace(output.result,report=replace(output.result.report,version=receipt.output.result.report.version)))
                if receipt.output != comparable:
                    raise ValueError('step_conflict: completed step output is immutable')
                return receipt
            for snapshot in output.snapshots:
                if snapshot.project_id != handle.project_id:
                    raise ProjectBoundaryError('step source crosses project scope')
                await self.research.write_snapshot(session,snapshot)
            if any(c.task_id != handle.task_id for c in output.claims):
                raise ProjectBoundaryError('step claim crosses task scope')
            await self.research.write_evidences(session,handle.project_id,output.evidences)
            await self.research.write_claims(session,handle.project_id,output.claims)
            for verification in output.verifications:
                claim = await session.get(ClaimRow,(handle.project_id,verification.claim_id))
                if claim is None or claim.task_id != handle.task_id:
                    raise ProjectBoundaryError('step verification crosses task scope')
            await self.research.write_verifications(session,handle.project_id,output.verifications)
            stored = output
            if output.result:
                if (output.result.project_id,output.result.task_id,output.result.run_id) != (handle.project_id,handle.task_id,handle.run_id):
                    raise ProjectBoundaryError('step report crosses run scope')
                stored = replace(output,result=await self.research.write_result(session,output.result))
            now = await self.now(session)
            row = StepRow(project_id=handle.project_id,run_id=handle.run_id,step_key=step_key,output=jsonable(stored),committed_at=now)
            session.add(row)
            self.event(session,run,'step_committed',now,{'step_key':step_key})
            await session.flush()
            await self.fence(session,handle)
            return self.receipt(row)

    async def finish(self, handle: RunHandle, state: RunState, error_code: str | None = None) -> RunRecord:
        if state not in {'succeeded','failed','cancelled','interrupted','awaiting_review'}:
            raise ValueError('invalid final or paused state')
        async with self.database.session.begin() as session:
            row = await self.fence(session,handle,allow_cancel=(state=='cancelled'))
            now = await self.now(session)
            budget=await session.get(BudgetRow,(handle.project_id,handle.run_id))
            if budget is not None:
                if budget.active:
                    elapsed=max(0.0,(now-budget.active_updated_at).total_seconds())
                    budget.active_elapsed_seconds=min(float(budget.limits['active_timeout_seconds']),budget.active_elapsed_seconds+elapsed)
                budget.active=False
                budget.active_updated_at=now
            row.state,row.error_code,row.updated_at,row.owner_id,row.lease_until = state,error_code,now,None,None
            self.event(session,row,state,now,{'error_code':error_code})
            return self.record(row)

    async def request_cancel(self, project_id: str, run_id: str) -> RunRecord:
        async with self.database.session.begin() as session:
            row = (await session.scalars(select(RunRow).where(RunRow.project_id==project_id,RunRow.run_id==run_id).with_for_update())).one_or_none()
            if row is None:
                raise ValueError('run not found in project')
            if row.state in {'succeeded','failed','cancelled'}:
                return self.record(row)
            now = await self.now(session)
            row.cancel_requested,row.updated_at = True,now
            if row.state in {'queued','awaiting_review','interrupted'}:
                row.state = 'cancelled'
            self.event(session,row,'cancel_requested',now)
            return self.record(row)

    async def list_events(self, project_id: str, run_id: str, after_id: int = 0) -> tuple[dict[str,Any],...]:
        async with self.database.session() as session:
            rows = (await session.scalars(select(EventRow).where(EventRow.project_id==project_id,EventRow.run_id==run_id,EventRow.event_id>after_id).order_by(EventRow.event_id).limit(100))).all()
            return tuple({'event_id':r.event_id,'run_id':r.run_id,'kind':r.kind,'data':r.data,'created_at':r.created_at.isoformat()} for r in rows)

    async def resume(self, project_id: str, run_id: str, input_version: str) -> RunRecord:
        async with self.database.session.begin() as session:
            row = (await session.scalars(select(RunRow).where(RunRow.project_id==project_id,RunRow.run_id==run_id).with_for_update())).one_or_none()
            if row is None:
                raise ValueError('run not found')
            if row.input_version != input_version:
                raise InputVersionMismatchError('run input version changed; create a new run')
            if row.state != 'interrupted' or row.cancel_requested:
                raise ValueError('run cannot be resumed from its current state')
            now = await self.now(session)
            row.state,row.owner_id,row.lease_until,row.updated_at = 'queued',None,None,now
            self.event(session,row,'resumed',now)
            return self.record(row)

    async def review(self, project_id: str, run_id: str, decision: ReviewDecision) -> RunRecord:
        async with self.database.session.begin() as session:
            row = (await session.scalars(select(RunRow).where(RunRow.project_id==project_id,RunRow.run_id==run_id).with_for_update())).one_or_none()
            if row is None or row.state != 'awaiting_review' or row.cancel_requested:
                raise ValueError('run is not awaiting review')
            now = await self.now(session)
            session.add(ReviewRow(project_id=project_id,run_id=run_id,decision=jsonable(decision),created_at=now))
            if decision.action=='approve':
                row.state = 'succeeded' if row.input_manifest['workflow_version']=='fixed-v1' else 'queued'
            else:
                row.state = 'cancelled'
            row.cancel_requested = decision.action=='reject'
            row.updated_at = now
            self.event(session,row,'reviewed',now,{'action':decision.action,'actor_id':decision.actor_id})
            return self.record(row)

    async def get_review(self, project_id: str, run_id: str) -> ReviewDecision | None:
        async with self.database.session() as session:
            row = await session.get(ReviewRow,(project_id,run_id))
            return decode_dataclass(ReviewDecision,row.decision) if row else None

    async def get_tool(self, handle: RunHandle, call_key: str) -> ToolResult | None:
        async with self.database.session.begin() as session:
            await self.fence(session,handle)
            row=await session.get(ToolRow,(handle.project_id,handle.run_id,call_key))
            return decode_dataclass(ToolResult,row.output) if row else None

    async def commit_tool(self, handle: RunHandle, call_key: str, result: ToolResult) -> ToolResult:
        async with self.database.session.begin() as session:
            run=await self.fence(session,handle)
            old=await session.get(ToolRow,(handle.project_id,handle.run_id,call_key))
            if old:
                return decode_dataclass(ToolResult,old.output)
            for snapshot in result.snapshots:
                if snapshot.project_id != handle.project_id:
                    raise ProjectBoundaryError('tool source crosses project boundary')
                await self.research.write_snapshot(session,snapshot)
                # Lexical derived chunks join the same fenced snapshot/receipt transaction.
                for chunk in chunk_snapshot(snapshot):
                    values={k:getattr(chunk,k) for k in ('project_id','chunk_id','snapshot_id','page','start','end','text')}
                    await session.execute(insert(ChunkRow).values(**values).on_conflict_do_nothing(index_elements=['project_id','chunk_id']))
            if result.follow_up:
                draft=result.follow_up
                if (draft.project_id,draft.parent_task_id)!=(handle.project_id,handle.task_id) or draft.started_run_id is not None:
                    raise ProjectBoundaryError('tool can only propose a draft for its own task')
                for cid in draft.claim_ids:
                    claim=await session.get(ClaimRow,(handle.project_id,cid))
                    if claim is None or claim.task_id != handle.task_id:
                        raise ProjectBoundaryError('draft claim is outside current task')
                session.add(FollowUpRow(project_id=draft.project_id,draft_id=draft.draft_id,parent_task_id=draft.parent_task_id,started_run_id=None,data=jsonable(draft)))
            now=await self.now(session)
            session.add(ToolRow(project_id=handle.project_id,run_id=handle.run_id,call_key=call_key,output=jsonable(result),committed_at=now))
            self.event(session,run,'tool_completed',now,{'name':result.name,'error_code':result.error_code})
            await session.flush()
            await self.fence(session,handle)
            return result
