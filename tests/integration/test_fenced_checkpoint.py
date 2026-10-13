import importlib

import pytest
from langgraph.checkpoint.base import empty_checkpoint
from sqlalchemy import text

from researchflow.domain.projects import Project, TaskRecord
from researchflow.infrastructure.storage.run_repository import RunRepository
from researchflow.ports.runtime import RunCancelledError, RunOwnershipLostError


def module():
    try:
        return importlib.import_module('researchflow.runtime.checkpointer')
    except ModuleNotFoundError:
        pytest.fail('JSON-only fenced graph checkpointer is not implemented')


@pytest.mark.asyncio
async def test_old_epoch_and_cancelled_worker_cannot_save_checkpoint_or_pending_writes(database,repository):
    cp=module()
    await repository.create_project(Project('p','Graph fencing'))
    await repository.save_task(TaskRecord('t','p','question'))
    runs=RunRepository(database,repository)
    record=await runs.enqueue('t','p','graph-v1',{'workflow_version':'graph-v1','execution_mode':'demo'})
    old=await runs.claim_next('old')
    saver=cp.FencedCheckpointer(database,runs,old)
    config={'configurable':{'thread_id':record.run_id,'checkpoint_ns':''}}
    checkpoint=empty_checkpoint()
    saved=await saver.aput(config,checkpoint,{'source':'input','step':-1,'parents':{}},{})
    async with database.session.begin() as session:
        await session.execute(text("UPDATE workflow_runs SET lease_until=clock_timestamp()-interval '1 second' WHERE run_id=:r"),{'r':record.run_id})
    fresh=await runs.recover_expired('new')
    for action in (saver.aput(config,empty_checkpoint(),{'step':0,'parents':{}},{}),saver.aput_writes(saved,[('foo','late')],'task')):
        with pytest.raises(RunOwnershipLostError):
            await action
    new_saver=cp.FencedCheckpointer(database,runs,fresh)
    assert (await new_saver.aget_tuple(config)).checkpoint['id']==checkpoint['id']
    await runs.request_cancel('p',record.run_id)
    with pytest.raises(RunCancelledError):
        await new_saver.aput_writes(saved,[('foo','cancelled')],'task')

