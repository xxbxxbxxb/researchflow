import importlib

import pytest

from researchflow.application.evidence import manual_evidence
from researchflow.domain.projects import Project, TaskRecord
from researchflow.domain.research import Evidence


def worker_modules():
    try:
        return (importlib.import_module('researchflow.runtime.fixed_workflow'),importlib.import_module('researchflow.runtime.worker'),importlib.import_module('researchflow.infrastructure.storage.run_repository'))
    except ModuleNotFoundError:
        pytest.fail('fixed durable worker not implemented')


@pytest.mark.asyncio
@pytest.mark.parametrize('with_sources',[True,False],ids=['supported','insufficient'])
async def test_durable_worker_builds_report_and_never_repeats_committed_steps(database,repository,with_sources):
    fixed, worker, run_module = worker_modules()
    from researchflow.infrastructure.llm.demo_model import DemoCaseModel
    from researchflow.infrastructure.storage.retrieval import PostgresRetriever
    await repository.create_project(Project('p','project',''))
    source_ids = ()
    if with_sources:
        snapshot, _ = manual_evidence('p',Evidence('e','fixture','p1','The synthetic study used a sample size of 12, only for Chinese text.'))
        await repository.save_snapshot(snapshot)
        await PostgresRetriever(database).index_snapshot(snapshot)
        source_ids = (snapshot.snapshot_id,)
    await repository.save_task(TaskRecord('t','p','synthetic study sample size',source_ids))
    runs = run_module.RunRepository(database,repository)
    record = await runs.enqueue('t','p','fixed-v1',input_manifest={'execution_mode':'demo','demo_case':'supported' if with_sources else 'insufficient'})
    workflow = fixed.FixedWorkflow(runs,repository,PostgresRetriever(database),DemoCaseModel('supported' if with_sources else 'insufficient'),execution_mode='demo')
    handle = await runs.claim_next('w')
    # The driver leaves the lease active until its last checkpoint/finish.
    outcome = await workflow.execute(handle)
    assert (await runs.get_run('p',record.run_id)).state == 'running'
    again = await workflow.execute(handle)
    assert again.report_id == outcome.report_id
    reports = await repository.list_reports('p','t')
    assert len(reports) == 1 and reports[0].version == 1
    assert bool(reports[0].conclusion_claim_ids) is with_sources
    await runs.finish(handle,'succeeded')
    assert not await worker.Worker(runs,workflow,'idle').run_once()
    record2 = await runs.enqueue('t','p','fixed-v1',input_manifest={'execution_mode':'demo','demo_case':'supported' if with_sources else 'insufficient'})
    assert await worker.Worker(runs,workflow,'second').run_once()
    assert (await runs.get_run('p',record2.run_id)).state == 'succeeded'
    assert sorted(r.version for r in await repository.list_reports('p','t')) == [1,2]


@pytest.mark.asyncio
async def test_worker_cli_once_executes_existing_database_run(database,repository,tmp_path):
    worker_modules()
    import asyncio
    import os
    import sys

    from researchflow.infrastructure.storage.run_repository import RunRepository
    await repository.create_project(Project('p','project',''))
    await repository.save_task(TaskRecord('cli','p','no sources'))
    runs = RunRepository(database,repository)
    record = await runs.enqueue('cli','p','fixed-v1',input_manifest={'execution_mode':'demo','demo_case':'insufficient'})
    process = await asyncio.create_subprocess_exec(sys.executable,'-m','researchflow.cli','worker','--once','--mode','demo',stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE,env={**os.environ,'RF_DATABASE_URL':database.url,'RF_BLOB_DIR':str(tmp_path/'blobs')})
    out,err = await process.communicate()
    assert process.returncode == 0,(out,err)
    assert (await runs.get_run('p',record.run_id)).state == 'succeeded'
