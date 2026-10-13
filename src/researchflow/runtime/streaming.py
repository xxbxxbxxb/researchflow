import asyncio
from contextlib import suppress
from uuid import uuid4

from researchflow.infrastructure.llm.errors import LLMProviderRateLimitError,LLMProviderUnavailableError
from researchflow.ports.runtime import RunOwnershipLostError,RunCancelledError
from researchflow.domain.usage import BudgetExceededError


class StreamInterruptedError(RuntimeError):
    """Content already delivered or stream ended without terminal acknowledgement."""


async def stream_model(runtime,handle,request):
    runtime.validate_context(request)
    snapshot=await runtime.tick(handle)
    timeout=min(snapshot.limits.operation_timeout_seconds,snapshot.limits.active_timeout_seconds-snapshot.active_elapsed_seconds)
    operation_id=uuid4().hex
    slot=False
    delivered=False
    attempt_id=None
    done=False
    deadline=runtime.clock()+timeout
    try:
        async with asyncio.timeout(timeout):
            while not slot:
                slot=await runtime.budgets.acquire_slot(handle,operation_id,timeout)
                if not slot:
                    await runtime.sleep(0.01)
            for attempt in range(1,runtime.max_attempts+1):
                attempt_id=uuid4().hex
                await runtime.budgets.begin_attempt(handle,attempt_id,request.operation,runtime.model_name)
                usage=None
                done=False
                iterator=runtime.provider.stream(request)
                try:
                    async for delta in iterator:
                        await runtime.tick(handle)
                        if delta.kind=='usage':
                            usage=delta.usage
                        if delta.kind=='text' and not delta.text:
                            continue
                        if delta.kind=='done':
                            done=True
                            await runtime.budgets.finish_attempt(handle,attempt_id,'succeeded',usage)
                        if delta.kind in ('text','tool_call'):
                            delivered=True
                        yield delta
                    if not done:
                        raise StreamInterruptedError('stream ended without done')
                    return
                except (LLMProviderUnavailableError,LLMProviderRateLimitError,StreamInterruptedError) as exc:
                    await runtime.budgets.finish_attempt(handle,attempt_id,'incomplete' if delivered else 'provider_failure',usage)
                    if delivered or attempt==runtime.max_attempts:
                        raise StreamInterruptedError('preview is incomplete; start a new generation') from exc
                    wait=getattr(exc,'retry_after_seconds',None)
                    wait=runtime.random(min(30,2**(attempt-1))) if wait is None else wait
                    if wait>=deadline-runtime.clock():
                        raise BudgetExceededError('stream retry exceeds operation deadline','operation') from exc
                    await runtime.sleep(wait)
                finally:
                    await iterator.aclose()
    finally:
        if attempt_id:
            with suppress(RunOwnershipLostError,RunCancelledError):
                if not done:
                    await runtime.budgets.finish_attempt(handle,attempt_id,'incomplete' if delivered else 'cancelled')
        if slot:
            with suppress(RunOwnershipLostError,RunCancelledError):
                await runtime.budgets.release_slot(handle,operation_id)
