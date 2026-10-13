import asyncio
import json
import random as random_module
import time
from contextlib import suppress
from dataclasses import asdict,replace
from typing import Callable
from uuid import uuid4

from researchflow.domain.runs import RunHandle
from researchflow.domain.usage import ModelUsage
from researchflow.infrastructure.llm.errors import LLMProviderRateLimitError,LLMProviderUnavailableError
from researchflow.ports.model import ChatModelPort,ChatRequest,ChatResponse
from researchflow.ports.runtime import RunOwnershipLostError,RunCancelledError
from researchflow.runtime.budget import BudgetExceededError,PriceConfig,price_usage
from researchflow.ports.telemetry import NullTrace


class ModelRuntime:
    """One budget/timeout/retry layer; delegates make one raw request."""
    def __init__(self, provider: ChatModelPort, budgets, context_window: int | None, price: PriceConfig | None = None, max_attempts: int = 3, random: Callable[[float],float] | None = None, sleep=asyncio.sleep, clock=time.monotonic, model_name: str = 'configured',trace=None) -> None:
        if type(context_window) is not int or context_window<=0:
            raise ValueError('context capacity must be configured')
        if type(max_attempts) is not int or not 1<=max_attempts<=3:
            raise ValueError('attempt limit must be one to three')
        self.provider,self.budgets,self.context_window,self.price=provider,budgets,context_window,price
        self.max_attempts,self.random,self.sleep,self.clock,self.model_name=max_attempts,random or (lambda high:random_module.uniform(0,high)),sleep,clock,model_name
        self.ticks:dict[tuple[str,int],float]={}
        self.tick_locks:dict[tuple[str,int],asyncio.Lock]={}
        self.trace=trace or NullTrace()

    async def tick(self, handle: RunHandle):
        key=(handle.run_id,handle.epoch)
        async with self.tick_locks.setdefault(key,asyncio.Lock()):
            now=self.clock()
            if key not in self.ticks:
                await self.budgets.ensure(handle)
            else:
                await self.budgets.charge(handle,max(0.0,now-self.ticks[key]))
            self.ticks[key]=now
            return await self.budgets.snapshot(handle)

    def validate_context(self, request: ChatRequest) -> None:
        if type(request.max_output_tokens) is not int or not 1<=request.max_output_tokens<=4096:
            raise BudgetExceededError('context output reservation is invalid','context')
        # Conservative UTF-8 byte estimate plus protocol overhead, not reported token usage.
        payload=json.dumps(asdict(request),ensure_ascii=False,allow_nan=False)
        estimate=len(payload.encode('utf-8'))+128*len(request.messages)+request.max_output_tokens
        if estimate>self.context_window:
            raise BudgetExceededError('context capacity would be exceeded; narrow the selected material','context')

    async def complete(self, handle: RunHandle, request: ChatRequest) -> ChatResponse:
        with self.trace.span('model',{'run_id':handle.run_id,'task_id':handle.task_id,'project_id':handle.project_id,'step_id':request.operation,'epoch':handle.epoch}):
            return await self._complete(handle,request)

    async def _complete(self, handle: RunHandle, request: ChatRequest) -> ChatResponse:
        self.validate_context(request)
        snapshot=await self.tick(handle)
        remaining=snapshot.limits.active_timeout_seconds-snapshot.active_elapsed_seconds
        timeout=min(snapshot.limits.operation_timeout_seconds,remaining)
        if timeout<=0:
            raise BudgetExceededError('operation deadline exhausted','operation')
        deadline=self.clock()+timeout
        operation_id=uuid4().hex
        slot=False
        attempt_id=None
        try:
            async with asyncio.timeout(timeout):
                while not slot:
                    slot=await self.budgets.acquire_slot(handle,operation_id,max(0.001,deadline-self.clock()))
                    if not slot:
                        await self.sleep(min(0.01,max(0.0,deadline-self.clock())))
                for attempt in range(1,self.max_attempts+1):
                    await self.tick(handle)
                    attempt_id=uuid4().hex
                    await self.budgets.begin_attempt(handle,attempt_id,request.operation,self.model_name)
                    try:
                        with self.trace.span('model.attempt',{'run_id':handle.run_id,'step_id':request.operation,'attempt_id':attempt_id,'model':self.model_name}):
                            response=await self.provider.complete(request)
                        await self.tick(handle)
                        usage=price_usage(response.usage,self.price) if response.usage is not None else None
                        await self.budgets.finish_attempt(handle,attempt_id,'succeeded',usage,response.model,response.request_id)
                        return replace(response,usage=usage)
                    except (LLMProviderRateLimitError,LLMProviderUnavailableError) as exc:
                        await self.budgets.finish_attempt(handle,attempt_id,'provider_failure')
                        if attempt>=self.max_attempts:
                            raise
                        wait=getattr(exc,'retry_after_seconds',None)
                        if wait is None:
                            wait=self.random(min(30.0,2.0**(attempt-1)))
                        remaining=deadline-self.clock()
                        if wait<0 or wait>=remaining:
                            raise BudgetExceededError('operation deadline cannot honor Retry-After/backoff','operation') from exc
                        await self.sleep(wait)
                    except asyncio.CancelledError:
                        with suppress(RunOwnershipLostError,RunCancelledError,BudgetExceededError):
                            await self.budgets.finish_attempt(handle,attempt_id,'cancelled')
                        raise
                    except Exception:
                        with suppress(RunOwnershipLostError,RunCancelledError,BudgetExceededError):
                            await self.budgets.finish_attempt(handle,attempt_id,'failed')
                        raise
                raise RuntimeError('attempt loop ended without an outcome')
        except TimeoutError as exc:
            if attempt_id:
                with suppress(RunOwnershipLostError,RunCancelledError,BudgetExceededError):
                    await self.budgets.finish_attempt(handle,attempt_id,'operation_timeout')
            raise BudgetExceededError('operation timeout exhausted','operation') from exc
        finally:
            if slot:
                with suppress(RunOwnershipLostError,RunCancelledError):
                    await self.budgets.release_slot(handle,operation_id)

    async def stream(self,handle: RunHandle,request: ChatRequest):
        from researchflow.runtime.streaming import stream_model
        iterator=stream_model(self,handle,request)
        try:
            async for delta in iterator:
                yield delta
        finally:
            await iterator.aclose()


class BoundChatModel:
    def __init__(self, runtime: ModelRuntime, handle: RunHandle) -> None:
        self.runtime,self.handle=runtime,handle

    async def complete(self, request: ChatRequest) -> ChatResponse:
        return await self.runtime.complete(self.handle,request)
