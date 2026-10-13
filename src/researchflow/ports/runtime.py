from typing import Protocol

from researchflow.domain.runs import RunHandle, RunOutcome, RunRecord, RunState, StepOutput, StepReceipt


class RunOwnershipLostError(RuntimeError):
    pass


class RunCancelledError(RuntimeError):
    pass


class InputVersionMismatchError(RuntimeError):
    pass


class RunRepositoryPort(Protocol):
    async def claim_next(self, owner_id: str) -> RunHandle | None: ...
    async def get_run(self, project_id: str, run_id: str) -> RunRecord | None: ...
    async def get_receipt(self, handle: RunHandle, step_key: str) -> StepReceipt | None: ...
    async def commit_step(self, handle: RunHandle, step_key: str, output: StepOutput) -> StepReceipt: ...
    async def heartbeat(self, handle: RunHandle) -> None: ...
    async def finish(self, handle: RunHandle, state: RunState, error_code: str | None = None) -> RunRecord: ...


class WorkflowPort(Protocol):
    async def execute(self, handle: RunHandle) -> RunOutcome: ...
