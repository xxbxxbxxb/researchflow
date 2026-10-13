import asyncio
import math
from dataclasses import dataclass, replace
from typing import Literal

from researchflow.domain.runs import RunHandle
from researchflow.domain.usage import BudgetExceededError as BudgetExceededError
from researchflow.domain.usage import ModelUsage, RunBudget, RunLimits
from researchflow.ports.runtime import RunOwnershipLostError

BudgetSnapshot=RunBudget


@dataclass(frozen=True)
class PriceConfig:
    version: str
    input_per_million: float
    output_per_million: float
    currency: str = 'USD'

    def __post_init__(self) -> None:
        if not self.version.strip() or self.currency!='USD':
            raise ValueError('price configuration needs an explicit USD version')
        if any(not math.isfinite(v) or v<0 for v in (self.input_per_million,self.output_per_million)):
            raise ValueError('price rates must be finite and nonnegative')


def price_usage(usage: ModelUsage, price: PriceConfig | None) -> ModelUsage:
    if price is None or usage.input_tokens is None or usage.output_tokens is None:
        return replace(usage,estimated_cost=None,price_version=None)
    cost=(usage.input_tokens*price.input_per_million+usage.output_tokens*price.output_per_million)/1_000_000
    return replace(usage,estimated_cost=cost,price_version=price.version)


def price_from_env():
    import os
    values=[os.getenv(k) for k in ('RF_PRICE_VERSION','RF_INPUT_PRICE_PER_MILLION','RF_OUTPUT_PRICE_PER_MILLION')]
    if not any(values):
        return None
    if not all(values):
        raise ValueError('price version and both USD rates must be configured together')
    return PriceConfig(values[0],float(values[1]),float(values[2]))


class MemoryBudgetRepository:
    """The same policy for a one-shot CLI run, whose process is not resumable."""
    def __init__(self, handle: RunHandle, limits: RunLimits | None = None) -> None:
        self.handle=handle
        self.budget=RunBudget(limits=limits or RunLimits())
        self.lock=asyncio.Lock()
        self.slots:set[str]=set()
        self.records:dict[str,dict]={}

    def fence(self, handle: RunHandle) -> None:
        if handle!=self.handle:
            raise RunOwnershipLostError('ephemeral run ownership differs')

    async def ensure(self, handle: RunHandle) -> BudgetSnapshot:
        self.fence(handle)
        return self.budget

    async def snapshot(self, handle: RunHandle) -> BudgetSnapshot:
        self.fence(handle)
        return self.budget

    async def reserve(self, handle: RunHandle, resource: Literal['model','tool','step'], amount: int = 1) -> BudgetSnapshot:
        async with self.lock:
            self.fence(handle)
            self.budget=self.budget.reserve(resource,amount)
            return self.budget

    async def charge(self, handle: RunHandle, seconds: float) -> BudgetSnapshot:
        async with self.lock:
            self.fence(handle)
            self.budget=self.budget.charge(seconds)
            return self.budget

    async def acquire_slot(self, handle: RunHandle, operation_id: str, seconds: float) -> bool:
        async with self.lock:
            self.fence(handle)
            if len(self.slots)>=self.budget.limits.max_concurrency:
                return False
            self.slots.add(operation_id)
            return True

    async def release_slot(self, handle: RunHandle, operation_id: str) -> None:
        async with self.lock:
            self.fence(handle)
            self.slots.discard(operation_id)

    async def begin_attempt(self, handle: RunHandle, attempt_id: str, operation: str, model: str) -> None:
        async with self.lock:
            self.fence(handle)
            self.budget=self.budget.reserve('model')
            self.records[attempt_id]={'attempt_id':attempt_id,'operation':operation,'model':model,'status':'pending','input_tokens':None,'output_tokens':None,'estimated_cost':None,'price_version':None}

    async def finish_attempt(self, handle: RunHandle, attempt_id: str, status: str, usage: ModelUsage | None = None, model: str | None = None, request_id: str | None = None) -> None:
        self.fence(handle)
        record=self.records[attempt_id]
        record['status']=status
        if model:
            record['model']=model
        if usage:
            record.update(input_tokens=usage.input_tokens,output_tokens=usage.output_tokens,estimated_cost=usage.estimated_cost,price_version=usage.price_version)

    async def record_usage(self, handle: RunHandle, attempt_id: str, usage: ModelUsage) -> None:
        await self.finish_attempt(handle,attempt_id,'succeeded',usage)

    async def list_usage(self, project_id: str, run_id: str) -> tuple[dict,...]:
        if (project_id,run_id)!=(self.handle.project_id,self.handle.run_id):
            return ()
        return tuple(self.records.values())
