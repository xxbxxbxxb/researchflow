import asyncio
import os
import sys

import pytest
from sqlalchemy import text

from researchflow.application.evidence import manual_evidence
from researchflow.domain.projects import Project, TaskRecord
from researchflow.domain.research import Evidence
from researchflow.infrastructure.llm.demo_model import CASES
from researchflow.infrastructure.storage.budget_repository import BudgetRepository
from researchflow.infrastructure.storage.retrieval import PostgresRetriever
from researchflow.infrastructure.storage.run_repository import RunRepository


@pytest.mark.asyncio
@pytest.mark.parametrize('crash_after', ['evidence', 'report'])
async def test_real_process_restart_skips_committed_business_steps(database, repository, crash_after):
    await repository.create_project(Project('p', 'Process restart'))
    snapshot, _ = manual_evidence('p', Evidence('e', 'fixture', 'p1', CASES['supported']['source']))
    await repository.save_snapshot(snapshot)
    await PostgresRetriever(database).index_snapshot(snapshot)
    await repository.save_task(TaskRecord('t', 'p', 'synthetic sample size', (snapshot.snapshot_id,)))
    runs = RunRepository(database, repository)
    record = await runs.enqueue('t', 'p', 'fixed-v1', {'execution_mode': 'demo'})
    script = '''
import asyncio, os
from researchflow.composition import worker_resources
async def main():
    async with worker_resources('demo','crash-worker') as worker:
        original = worker.runs.commit_step
        async def pause(handle,key,output):
            receipt = await original(handle,key,output)
            if key == os.environ['CRASH_AFTER']:
                print('COMMITTED',flush=True)
                await asyncio.Future()
            return receipt
        worker.runs.commit_step = pause
        await worker.run_once()
asyncio.run(main())
'''
    env = {**os.environ, 'RF_DATABASE_URL': database.url, 'CRASH_AFTER': crash_after}
    child = await asyncio.create_subprocess_exec(sys.executable, '-c', script, env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        assert await asyncio.wait_for(child.stdout.readline(), 15) == b'COMMITTED\n'
    finally:
        child.kill()
        await child.wait()
    before = await BudgetRepository(database).read_snapshot('p', record.run_id)
    async with database.session.begin() as session:
        await session.execute(text("UPDATE workflow_runs SET lease_until=clock_timestamp()-interval '1 second' WHERE run_id=:id"), {'id': record.run_id})
    from researchflow.composition import worker_resources
    os.environ['RF_DATABASE_URL'] = database.url
    async with worker_resources('demo', 'restarted-worker') as worker:
        assert await worker.run_once()
    after = await BudgetRepository(database).read_snapshot('p', record.run_id)
    restored = await runs.get_run('p', record.run_id)
    assert restored.state == 'succeeded' and restored.epoch == 2
    assert len(await repository.list_reports('p', 't')) == 1
    assert after.model_calls_used >= before.model_calls_used
    if crash_after == 'report':
        assert after.model_calls_used == before.model_calls_used == 2

