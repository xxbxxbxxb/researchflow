from dataclasses import replace
from datetime import timedelta
from typing import Literal

from sqlalchemy import select,func,delete
from sqlalchemy.ext.asyncio import AsyncSession

from researchflow.domain.runs import RunHandle
from researchflow.domain.usage import RunBudget,RunLimits,ModelUsage,BudgetExceededError
from researchflow.infrastructure.storage.codec import jsonable,decode_dataclass
from researchflow.infrastructure.storage.database import Database
from researchflow.infrastructure.storage.models import BudgetRow,UsageRow,OperationSlotRow
from researchflow.infrastructure.storage.run_repository import RunRepository


class BudgetRepository:
    def __init__(self, database: Database, runs: RunRepository | None = None, limits: RunLimits | None = None) -> None:
        self.database,self.runs,self.limits=database,runs or RunRepository(database),limits or RunLimits()

    def value(self, row: BudgetRow) -> RunBudget:
        return RunBudget(row.model_calls_used,row.tool_calls_used,row.steps_used,row.active_elapsed_seconds,decode_dataclass(RunLimits,row.limits))

    def apply(self, row: BudgetRow, value: RunBudget) -> None:
        for name in ('model_calls_used','tool_calls_used','steps_used','active_elapsed_seconds'):
            setattr(row,name,getattr(value,name))

    async def row_in(self, session: AsyncSession, handle: RunHandle) -> BudgetRow:
        await self.runs.fence(session,handle)
        row=(await session.scalars(select(BudgetRow).where(BudgetRow.project_id==handle.project_id,BudgetRow.run_id==handle.run_id).with_for_update())).one_or_none()
        if row is None:
            now=await self.runs.now(session)
            row=BudgetRow(project_id=handle.project_id,run_id=handle.run_id,limits=jsonable(self.limits),model_calls_used=0,tool_calls_used=0,steps_used=0,active_elapsed_seconds=0.0,active_updated_at=now,active_epoch=handle.epoch,active=True)
            session.add(row)
            await session.flush()
        return row

    async def ensure(self, handle: RunHandle) -> RunBudget:
        async with self.database.session.begin() as session:
            row=await self.row_in(session,handle)
            # The stored limits and consumed counters remain authoritative on recovery.
            if row.active_epoch != handle.epoch or not row.active:
                row.active_updated_at = await self.runs.now(session)
            row.active_epoch,row.active=handle.epoch,True
            return self.value(row)

    async def snapshot(self, handle: RunHandle) -> RunBudget:
        async with self.database.session.begin() as session:
            return self.value(await self.row_in(session,handle))

    async def reserve(self, handle: RunHandle, resource: Literal['model','tool','step'], amount: int = 1) -> RunBudget:
        async with self.database.session.begin() as session:
            row=await self.row_in(session,handle)
            budget=self.value(row).reserve(resource,amount)
            self.apply(row,budget)
            return budget

    async def charge(self, handle: RunHandle, seconds: float) -> RunBudget:
        exhausted=False
        async with self.database.session.begin() as session:
            row=await self.row_in(session,handle)
            current=self.value(row)
            try:
                budget=current.charge(seconds)
            except BudgetExceededError:
                exhausted=True
                budget=replace(current,active_elapsed_seconds=current.limits.active_timeout_seconds)
            self.apply(row,budget)
            row.active_updated_at=await self.runs.now(session)
        if exhausted:
            raise BudgetExceededError('active run deadline exhausted','active')
        return budget

    async def acquire_slot(self, handle: RunHandle, operation_id: str, seconds: float) -> bool:
        async with self.database.session.begin() as session:
            row=await self.row_in(session,handle)
            now=await self.runs.now(session)
            await session.execute(delete(OperationSlotRow).where(OperationSlotRow.project_id==handle.project_id,OperationSlotRow.run_id==handle.run_id,OperationSlotRow.expires_at<=now))
            count=await session.scalar(select(func.count()).select_from(OperationSlotRow).where(OperationSlotRow.project_id==handle.project_id,OperationSlotRow.run_id==handle.run_id))
            if (count or 0)>=self.value(row).limits.max_concurrency:
                return False
            session.add(OperationSlotRow(project_id=handle.project_id,run_id=handle.run_id,operation_id=operation_id,epoch=handle.epoch,expires_at=now+timedelta(seconds=seconds)))
            return True

    async def release_slot(self, handle: RunHandle, operation_id: str) -> None:
        async with self.database.session.begin() as session:
            await self.runs.fence(session,handle,allow_cancel=True)
            await session.execute(delete(OperationSlotRow).where(OperationSlotRow.project_id==handle.project_id,OperationSlotRow.run_id==handle.run_id,OperationSlotRow.operation_id==operation_id,OperationSlotRow.epoch==handle.epoch))

    async def begin_attempt(self, handle: RunHandle, attempt_id: str, operation: str, model: str) -> None:
        async with self.database.session.begin() as session:
            row=await self.row_in(session,handle)
            self.apply(row,self.value(row).reserve('model'))
            now=await self.runs.now(session)
            session.add(UsageRow(project_id=handle.project_id,run_id=handle.run_id,attempt_id=attempt_id,epoch=handle.epoch,operation=operation[:100],model=model[:200],status='pending',created_at=now))

    async def finish_attempt(self, handle: RunHandle, attempt_id: str, status: str, usage: ModelUsage | None = None, model: str | None = None, request_id: str | None = None) -> None:
        async with self.database.session.begin() as session:
            await self.runs.fence(session,handle)
            row=(await session.scalars(select(UsageRow).where(UsageRow.project_id==handle.project_id,UsageRow.run_id==handle.run_id,UsageRow.attempt_id==attempt_id,UsageRow.epoch==handle.epoch).with_for_update())).one_or_none()
            if row is None:
                raise ValueError('attempt does not belong to current run ownership')
            row.status=status
            row.completed_at=await self.runs.now(session)
            if isinstance(model,str) and model:
                row.model=model[:200]
            if isinstance(request_id,str):
                row.request_id=request_id[:200]
            if usage is not None:
                row.input_tokens,row.output_tokens,row.estimated_cost,row.price_version=usage.input_tokens,usage.output_tokens,usage.estimated_cost,usage.price_version

    async def record_usage(self, handle: RunHandle, attempt_id: str, usage: ModelUsage) -> None:
        await self.finish_attempt(handle,attempt_id,'succeeded',usage)

    async def list_usage(self, project_id: str, run_id: str) -> tuple[dict,...]:
        async with self.database.session() as session:
            rows=(await session.scalars(select(UsageRow).where(UsageRow.project_id==project_id,UsageRow.run_id==run_id).order_by(UsageRow.created_at,UsageRow.attempt_id))).all()
            return tuple({'attempt_id':row.attempt_id,'epoch':row.epoch,'operation':row.operation,'model':row.model,'status':row.status,'input_tokens':row.input_tokens,'output_tokens':row.output_tokens,'estimated_cost':row.estimated_cost,'price_version':row.price_version,'request_id':row.request_id,'created_at':row.created_at.isoformat()} for row in rows)

    async def read_snapshot(self, project_id: str, run_id: str) -> RunBudget | None:
        async with self.database.session() as session:
            row=await session.get(BudgetRow,(project_id,run_id))
            return self.value(row) if row else None

    async def pause(self, handle: RunHandle) -> None:
        async with self.database.session.begin() as session:
            row=await self.row_in(session,handle)
            row.active=False
            row.active_updated_at=await self.runs.now(session)
