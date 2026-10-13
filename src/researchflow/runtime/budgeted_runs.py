from researchflow.domain.runs import RunHandle,RunState,StepOutput
from researchflow.runtime.model_runtime import ModelRuntime


class BudgetedRuns:
    """Phase execution checks share the same active clock as all model attempts."""
    def __init__(self, repository, runtime: ModelRuntime) -> None:
        self.repository,self.runtime=repository,runtime

    async def get_run(self, project_id: str, run_id: str):
        return await self.repository.get_run(project_id,run_id)

    async def get_receipt(self, handle: RunHandle, step_key: str):
        await self.runtime.tick(handle)
        return await self.repository.get_receipt(handle,step_key)

    async def commit_step(self, handle: RunHandle, step_key: str, output: StepOutput):
        await self.runtime.tick(handle)
        return await self.repository.commit_step(handle,step_key,output)

    async def heartbeat(self, handle: RunHandle) -> None:
        await self.repository.heartbeat(handle)
        await self.runtime.tick(handle)

    async def finish(self, handle: RunHandle, state: RunState, error_code: str | None = None):
        return await self.repository.finish(handle,state,error_code)
