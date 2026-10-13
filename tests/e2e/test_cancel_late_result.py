import asyncio
import pytest

from researchflow.domain.runs import StepOutput, RunOutcome
from researchflow.ports.runtime import RunCancelledError
from researchflow.runtime.worker import Worker
from researchflow.domain.projects import Project, TaskRecord
from researchflow.infrastructure.storage.run_repository import RunRepository


async def setup_run(database, repository):
    await repository.create_project(Project('p', 'Cancel'))
    await repository.save_task(TaskRecord('t', 'p', 'fixture question'))
    runs = RunRepository(database, repository)
    record = await runs.enqueue('t', 'p', 'stable-input', {'execution_mode': 'demo'})
    return runs, record, await runs.claim_next('old-owner')


@pytest.mark.asyncio
async def test_cancellation_closes_active_task_and_rejects_result_even_if_provider_ignores_cancel(database, repository):
    runs, record, old = await setup_run(database, repository)
    await runs.finish(old, 'interrupted')
    await runs.resume('p', record.run_id, 'stable-input')
    started, closed = asyncio.Event(), asyncio.Event()
    class Workflow:
        async def execute(self, handle):
            started.set()
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                closed.set()
                with pytest.raises(RunCancelledError):
                    await runs.commit_step(handle, 'late-report', StepOutput())
                raise
            return RunOutcome('succeeded')
    task = asyncio.create_task(Worker(runs, Workflow(), 'cancel-worker', heartbeat_seconds=0.01).run_once())
    await asyncio.wait_for(started.wait(), 2)
    await runs.request_cancel('p', record.run_id)
    await asyncio.wait_for(task, 2)
    assert closed.is_set()
    assert (await runs.get_run('p', record.run_id)).state == 'cancelled'
    assert await repository.list_reports('p', 't') == ()
