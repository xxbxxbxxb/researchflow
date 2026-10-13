import pytest
from sqlalchemy import text

from researchflow.domain.projects import Project, TaskRecord
from researchflow.domain.runs import StepOutput
from researchflow.infrastructure.storage.budget_repository import BudgetRepository
from researchflow.infrastructure.storage.run_repository import RunRepository
from researchflow.ports.runtime import InputVersionMismatchError, RunCancelledError, RunOwnershipLostError


async def setup_run(database, repository):
    await repository.create_project(Project('p', 'Recovery'))
    await repository.save_task(TaskRecord('t', 'p', 'fixture question'))
    runs = RunRepository(database, repository)
    record = await runs.enqueue('t', 'p', 'stable-input', {'execution_mode': 'demo'})
    return runs, record, await runs.claim_next('old-owner')


async def expire(database, run_id):
    async with database.session.begin() as session:
        await session.execute(text("UPDATE workflow_runs SET lease_until=clock_timestamp()-interval '1 second' WHERE run_id=:id"), {'id': run_id})


@pytest.mark.asyncio
async def test_expired_owner_cannot_write_and_recovery_keeps_budget(database, repository):
    runs, record, old = await setup_run(database, repository)
    budgets = BudgetRepository(database, runs)
    await budgets.reserve(old, 'model', 3)
    await runs.commit_step(old, 'collect', StepOutput(data={'source_ids': []}))
    await expire(database, record.run_id)
    with pytest.raises(RunOwnershipLostError):
        await runs.commit_step(old, 'evidence', StepOutput())
    assert hasattr(runs, 'recover_expired'), 'expired runs need automatic recovery, not a new task'
    new = await runs.recover_expired('new-owner')
    assert new.run_id == old.run_id and new.epoch > old.epoch
    assert (await budgets.snapshot(new)).model_calls_used == 3
    assert (await runs.get_receipt(new, 'collect')).output.data == {'source_ids': []}
    with pytest.raises(RunOwnershipLostError):
        await runs.commit_step(old, 'evidence', StepOutput())


@pytest.mark.asyncio
async def test_cancel_blocks_late_business_commit_and_stale_heartbeat(database, repository):
    runs, record, handle = await setup_run(database, repository)
    await runs.request_cancel('p', record.run_id)
    with pytest.raises(RunCancelledError):
        await runs.commit_step(handle, 'late', StepOutput())
    with pytest.raises(RunCancelledError):
        await runs.heartbeat(handle)
    await expire(database, record.run_id)
    assert hasattr(runs, 'recover_expired')
    assert await runs.recover_expired('replacement') is None
    assert (await runs.get_run('p', record.run_id)).state == 'cancelled'


@pytest.mark.asyncio
async def test_resume_rejects_changed_input_version(database, repository):
    runs, record, handle = await setup_run(database, repository)
    await runs.finish(handle, 'interrupted')
    with pytest.raises(InputVersionMismatchError):
        await runs.resume('p', record.run_id, 'changed-policy')
    assert (await runs.get_run('p', record.run_id)).state == 'interrupted'

