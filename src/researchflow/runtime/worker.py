import asyncio
from contextlib import suppress

from researchflow.ports.runtime import RunRepositoryPort, WorkflowPort, RunCancelledError, RunOwnershipLostError, InputVersionMismatchError


class Worker:
    def __init__(self, runs: RunRepositoryPort, workflow: WorkflowPort, owner_id: str, heartbeat_seconds: float = 1.0) -> None:
        self.runs,self.workflow,self.owner_id,self.heartbeat_seconds = runs,workflow,owner_id,heartbeat_seconds

    async def pulse(self, handle) -> None:
        while True:
            await asyncio.sleep(self.heartbeat_seconds)
            await self.runs.heartbeat(handle)

    async def run_once(self) -> bool:
        handle = await self.runs.claim_next(self.owner_id)
        if handle is None:
            return False
        execution = asyncio.create_task(self.workflow.execute(handle))
        heartbeat = asyncio.create_task(self.pulse(handle))
        try:
            done,_ = await asyncio.wait({execution,heartbeat},return_when=asyncio.FIRST_COMPLETED)
            if heartbeat in done:
                heartbeat.result()
            outcome = await execution
            await self.runs.finish(handle,outcome.state)
        except RunCancelledError:
            with suppress(RunOwnershipLostError):
                await self.runs.finish(handle,'cancelled')
        except RunOwnershipLostError:
            pass  # a new owner, never this Worker, decides the current state
        except asyncio.CancelledError:
            with suppress(RunOwnershipLostError,RunCancelledError):
                await self.runs.finish(handle,'interrupted','worker_shutdown')
            raise
        except Exception as exc:
            with suppress(RunOwnershipLostError,RunCancelledError):
                code = 'input_version_mismatch' if isinstance(exc,InputVersionMismatchError) else 'execution_failed'
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
