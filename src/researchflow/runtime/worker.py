import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Literal

from researchflow.domain.runs import RunHandle
from researchflow.domain.usage import BudgetExceededError
from researchflow.ports.runtime import (
    InputVersionMismatchError,
    RunCancelledError,
    RunOwnershipLostError,
    RunRepositoryPort,
    WorkflowPort,
)
from researchflow.ports.telemetry import NullTrace, RuntimeFailure


class Worker:
    def __init__(self, runs: RunRepositoryPort, workflow: WorkflowPort, owner_id: str, heartbeat_seconds: float = 1.0, on_heartbeat: Callable[[RunHandle],Awaitable[None]] | None = None,trace=None) -> None:
        self.runs,self.workflow,self.owner_id,self.heartbeat_seconds = runs,workflow,owner_id,heartbeat_seconds
        self.on_heartbeat=on_heartbeat
        self.trace=trace or NullTrace()

    async def pulse(self, handle) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            await self.runs.heartbeat(handle)
            if self.on_heartbeat is not None:
                await self.on_heartbeat(handle)

    async def run_once(self) -> bool:
        return await self._run_once()

    async def _run_once(self) -> bool:
        handle = await self.runs.claim_next(self.owner_id)
        if handle is None:
            handle = await self.runs.recover_expired(self.owner_id)
        if handle is None:
            return False
        async def traced_execution():
            with self.trace.span('research.run',{'run_id':handle.run_id,'task_id':handle.task_id,'project_id':handle.project_id,'epoch':handle.epoch}):
                return await self.workflow.execute(handle)
        execution = asyncio.create_task(traced_execution())
        heartbeat = asyncio.create_task(self.pulse(handle))
        try:
            done,_ = await asyncio.wait({execution,heartbeat},return_when=asyncio.FIRST_COMPLETED)
            if heartbeat in done:
                heartbeat.result()
            outcome = await execution
            await self.runs.finish(handle,outcome.state)
        except RunCancelledError:
            execution.cancel()
            await asyncio.gather(execution,return_exceptions=True)
            with suppress(RunOwnershipLostError):
                await self.runs.finish(handle,'cancelled')
        except RunOwnershipLostError:
            pass  # a new owner, never this Worker, decides the current state
        except asyncio.CancelledError:
            with suppress(RunOwnershipLostError,RunCancelledError):
                await self.runs.finish(handle,'interrupted','worker_shutdown')
            raise
        except Exception as exc:
            kind: Literal['budget','protocol','provider','persistence']='budget' if isinstance(exc,BudgetExceededError) else 'protocol' if 'Protocol' in type(exc).__name__ else 'provider' if 'Provider' in type(exc).__name__ else 'persistence'
            self.trace.record_failure(RuntimeFailure(kind,handle.run_id,'workflow',type(exc).__name__))
            with suppress(RunOwnershipLostError,RunCancelledError):
                if hasattr(self.runs,'record_failure'):
                    await self.runs.record_failure(handle,kind,exc)
                code = 'input_version_mismatch' if isinstance(exc,InputVersionMismatchError) else 'budget_exceeded' if isinstance(exc,BudgetExceededError) else 'execution_failed'
                await self.runs.finish(handle,'failed',code)
        finally:
            for task in (execution,heartbeat):
                task.cancel()
            await asyncio.gather(execution,heartbeat,return_exceptions=True)
        return True

    async def run_forever(self) -> None:
        while True:
            if not await self.run_once():
                await asyncio.sleep(0.5)
