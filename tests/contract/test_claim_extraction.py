import importlib
import json

import pytest

from researchflow.application.evidence import manual_evidence
from researchflow.domain.research import Evidence


def api():
    if importlib.util.find_spec('researchflow.application.claims') is None:
        pytest.fail('Structured claim extraction is not implemented')
    return importlib.import_module('researchflow.application.claims'), importlib.import_module('researchflow.ports.model'), importlib.import_module('researchflow.domain.projects')


class SequenceModel:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0
        self.requests = []
    async def complete(self, request):
        _, types, _ = api()
        self.requests.append(request)
        text = self.outputs[min(self.calls, len(self.outputs)-1)]
        self.calls += 1
        return types.ChatResponse(text=text, model='fixture')


def fixture():
    app, _, types = api()
    task = types.TaskRecord('task-a', 'project-a', 'What was the sample size?', (), None)
    _, item = manual_evidence('project-a', Evidence('t:E001', 'paper', 'p1', 'The sample size was 12.'))
    return app, task, item


def payload(text='The sample size was 12.', ids=None):
    return {'text': text, 'evidence_ids': ids if ids is not None else ['t:E001'], 'qualifiers': []}


@pytest.mark.asyncio
async def test_extracts_and_deduplicates_atomic_claims():
    app, task, item = fixture()
    model = SequenceModel([json.dumps({'claims':[payload(),payload(),payload('The study uses human data.')]})])
    claims = await app.ClaimExtractor(model).extract(task, (item,))
    assert len(claims) == 2
    assert claims[0].proposed_evidence_ids == ('t:E001',)
    assert claims[0].project_id == 'project-a'
    assert model.requests[0].messages[0].role == 'system'
    assert model.requests[0].messages[1].role == 'user'


@pytest.mark.asyncio
async def test_only_one_structural_repair_is_permitted():
    app, task, item = fixture()
    model = SequenceModel(['bad json',json.dumps({'claims':[payload()]})])
    claims = await app.ClaimExtractor(model).extract(task, (item,))
    assert len(claims) == 1 and model.calls == 2
    failed = SequenceModel(['bad json'])
    with pytest.raises(ValueError):
        await app.ClaimExtractor(failed).extract(task, (item,))
    assert failed.calls == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('claims', [[payload(ids=['E999'])], [payload('x'*2001)], [payload()]*13])
async def test_rejects_invalid_reference_and_output_bounds(claims):
    app, task, item = fixture()
    model = SequenceModel([json.dumps({'claims':claims})])
    with pytest.raises(ValueError):
        await app.ClaimExtractor(model).extract(task, (item,))


@pytest.mark.asyncio
async def test_cross_project_evidence_is_rejected_before_model_call():
    app, task, _ = fixture()
    _, item = manual_evidence('another-project', Evidence('other', 'paper', 'p1', 'sample 99'))
    model = SequenceModel(['{}'])
    with pytest.raises(ValueError):
        await app.ClaimExtractor(model).extract(task, (item,))
    assert model.calls == 0


@pytest.mark.asyncio
async def test_empty_or_refused_output_is_not_a_claim():
    app, task, item = fixture()
    for output in ['', 'I cannot comply']:
        with pytest.raises(ValueError):
            await app.ClaimExtractor(SequenceModel([output])).extract(task, (item,))


@pytest.mark.asyncio
async def test_changed_evidence_binding_produces_new_claim_identity():
    app, task, item = fixture()
    _, other = manual_evidence("project-a", Evidence("t:E002", "replication", "p2", "The sample size was 12."))
    first = (await app.ClaimExtractor(SequenceModel([json.dumps({"claims":[payload()]})])).extract(task,(item,)))[0]
    second = (await app.ClaimExtractor(SequenceModel([json.dumps({"claims":[payload(ids=["t:E002"])]})])).extract(task,(other,)))[0]
    assert first.claim_id != second.claim_id
