import asyncio
import importlib
from dataclasses import replace

import pytest

from researchflow.application.evidence import manual_evidence
from researchflow.domain.projects import Project, TaskRecord
from researchflow.domain.research import Evidence


def modules():
    try:
        return (importlib.import_module('researchflow.infrastructure.storage.run_repository'), importlib.import_module('researchflow.domain.runs'), importlib.import_module('researchflow.ports.runtime'))
    except ModuleNotFoundError:
        pytest.fail('durable run/step transaction not implemented')


async def setup(repository, database):
    m, types, errors = modules()
    await repository.create_project(Project('p','project',''))
    snapshot, evidence = manual_evidence('p',Evidence('e1','fixture','p1','The synthetic study used a sample size of 12, only for Chinese text.'))
    await repository.save_snapshot(snapshot)
    await repository.save_task(TaskRecord('t','p','sample size',(snapshot.snapshot_id,)))
    runs = m.RunRepository(database,repository)
    record = await runs.enqueue('t','p','fixed-v1',input_manifest={'execution_mode':'demo','demo_case':'supported','model_version':'demo:fixed-case-v1'})
    return runs, record, evidence


@pytest.mark.asyncio
async def test_claim_is_exclusive_and_inputs_capture_versions(database,repository):
    runs, record, evidence = await setup(repository,database)
    first, second = await asyncio.gather(runs.claim_next('w1'), runs.claim_next('w2'))
    assert sum(handle is not None for handle in (first,second)) == 1
    assert record.input_manifest['sources'][0]['snapshot_id'] == evidence.anchor.snapshot_id
    assert record.input_manifest['workflow_version'] == 'fixed-v1'
    assert record.input_manifest['prompt_version'] and record.input_manifest['parser_versions']


@pytest.mark.asyncio
async def test_step_and_business_batch_are_atomic_then_idempotent(database,repository):
    runs, record, evidence = await setup(repository,database)
    _, types, errors = modules()
    handle = await runs.claim_next('w1')
    conflicting = replace(evidence,evidence=replace(evidence.evidence,text='forged text'))
    with pytest.raises(ValueError):
        await runs.commit_step(handle,'evidence',types.StepOutput(evidences=(evidence,conflicting)))
    assert await repository.get_evidence('p','e1') is None
    assert await runs.get_receipt(handle,'evidence') is None
    output = types.StepOutput(data={'source_mode':'lexical'},evidences=(evidence,))
    first = await runs.commit_step(handle,'evidence',output)
    second = await runs.commit_step(handle,'evidence',output)
    assert first == second
    assert (await repository.get_evidence('p','e1')) == evidence
    assert len(await runs.list_events('p',record.run_id)) == 3  # queued, claimed, committed
    with pytest.raises(ValueError, match='step_conflict'):
        await runs.commit_step(handle,'evidence',types.StepOutput(data={'different':True}))


@pytest.mark.asyncio
async def test_wrong_epoch_project_and_cancelled_handle_cannot_write(database,repository):
    runs, record, evidence = await setup(repository,database)
    _, types, errors = modules()
    handle = await runs.claim_next('w1')
    for changed in (replace(handle,epoch=handle.epoch+1),replace(handle,project_id='other')):
        with pytest.raises(errors.RunOwnershipLostError):
            await runs.commit_step(changed,'evidence',types.StepOutput(evidences=(evidence,)))
    await runs.request_cancel('p',record.run_id)
    with pytest.raises(errors.RunCancelledError):
        await runs.commit_step(handle,'evidence',types.StepOutput(evidences=(evidence,)))
    assert await repository.get_evidence('p','e1') is None
