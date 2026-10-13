import importlib

import pytest

from researchflow.application.evidence import manual_evidence
from researchflow.domain.projects import Project, TaskRecord
from researchflow.domain.research import Evidence


def service(repository,database):
    try:
        module = importlib.import_module('researchflow.application.knowledge')
        storage = importlib.import_module('researchflow.infrastructure.storage.knowledge_repository')
    except ModuleNotFoundError:
        pytest.fail('reviewed knowledge and follow-up lineage not implemented')
    port = storage.KnowledgeRepository(database,repository)
    return module.KnowledgeService(port),port


async def report(repository):
    from researchflow.application.research import ResearchService
    from researchflow.infrastructure.llm.demo_model import CASES, DemoCaseModel
    await repository.create_project(Project('p','Knowledge project'))
    task = TaskRecord('t','p','What is the sample size?')
    await repository.save_task(task)
    snapshot,evidence = manual_evidence('p',Evidence('e1','synthetic','p1',CASES['supported']['source']))
    await repository.save_snapshot(snapshot)
    result = await ResearchService(DemoCaseModel(),'demo').run_manual(task,(snapshot,),(evidence,),'run')
    await repository.save_result(result)
    return result


@pytest.mark.asyncio
async def test_accept_is_supported_only_scoped_idempotent_and_keeps_provenance(database,repository):
    knowledge,port = service(repository,database)
    result = await report(repository)
    verification = result.verifications[0]
    entry = await knowledge.accept('p',verification.verification_id,'owner')
    again = await knowledge.accept('p',verification.verification_id,'owner')
    assert entry == again and entry.accepted_by == 'owner' and entry.accepted_at.tzinfo
    assert entry.report_id == result.report.report_id and entry.verification_id == verification.verification_id
    with pytest.raises(ValueError):
        await knowledge.accept('other',verification.verification_id,'owner')
    context = await port.verification_context('p',verification.verification_id)
    assert context.result.evidences[0].evidence.text == result.evidences[0].evidence.text


@pytest.mark.asyncio
async def test_manual_override_keeps_old_report_and_requires_explicit_supersession(database,repository):
    knowledge,port = service(repository,database)
    result = await report(repository)
    old = result.verifications[0]
    entry = await knowledge.accept('p',old.verification_id,'owner')
    with pytest.raises(ValueError,match='reason'):
        await knowledge.override('p',old.verification_id,'contradicted','','owner')
    new = await knowledge.override('p',old.verification_id,'contradicted','Reinspection reveals conflicting experimental conditions.','owner')
    assert new.actor=='owner' and new.supersedes_id==old.verification_id
    assert (await repository.get_result('p',result.report.report_id)).verifications[0] == old
    assert (await port.list_entries('p'))[0].status == 'active'
    with pytest.raises(ValueError,match='supported|current'):
        await knowledge.accept('p',new.verification_id,'owner')
    with pytest.raises(ValueError,match='current'):
        await knowledge.accept('p',old.verification_id,'owner')
    replacement = await knowledge.supersede('p',entry.knowledge_id,new.verification_id,'owner')
    assert replacement.supersedes_id == entry.knowledge_id and replacement.status=='active'
    history = await port.list_entries('p')
    assert next(e for e in history if e.knowledge_id==entry.knowledge_id).status=='superseded'
    assert await knowledge.supersede('p',entry.knowledge_id,new.verification_id,'owner') == replacement
    assert (await repository.get_result('p',result.report.report_id)).report == result.report
    assert len(await repository.list_reports('p','t')) == 2


@pytest.mark.asyncio
async def test_follow_up_is_only_a_draft_preserving_parent_and_claim_relations(database,repository):
    knowledge,port = service(repository,database)
    result = await report(repository)
    draft = await knowledge.draft_follow_up('p','t','Which experimental condition should be checked?',(result.claims[0].claim_id,))
    assert draft.parent_task_id=='t' and draft.started_run_id is None
    assert draft.claim_ids == (result.claims[0].claim_id,)
    assert len(await repository.list_tasks('p'))==1
    from researchflow.infrastructure.storage.run_repository import RunRepository
    assert not await RunRepository(database).list_runs('p')
    with pytest.raises(ValueError):
        await knowledge.draft_follow_up('p','t','Bad scope',('not-a-claim',))


@pytest.mark.asyncio
async def test_fixed_workflow_pauses_after_report_and_authorized_review_finishes_without_model(database,tmp_path):
    from test_task_api import authenticated_api

    from researchflow.runtime.fixed_workflow import FixedWorkflow
    from researchflow.runtime.worker import Worker
    async with authenticated_api(database,tmp_path) as (client,app):
        resources = app.state.resources
        pid = (await client.post('/api/projects',json={'name':'Review project'})).json()['project_id']
        tid = (await client.post(f'/api/projects/{pid}/tasks',json={'question':'No sources'})).json()['task_id']
        response = await client.post(f'/api/tasks/{tid}/runs',json={'project_id':pid,'mode':'demo','require_review':True},headers={'idempotency-key':'review'})
        assert response.status_code == 201,response.text
        rid = response.json()['run_id']
        class NoModel:
            calls = 0
            async def complete(self,request):
                self.calls += 1
                pytest.fail('an empty-source review must not call a model')
        model = NoModel()
        workflow = FixedWorkflow(resources.runs,resources.research,resources.retriever,model,'demo')
        await Worker(resources.runs,workflow,'review-worker').run_once()
        assert (await resources.runs.get_run(pid,rid)).state == 'awaiting_review'
        reports = await resources.research.list_reports(pid,tid)
        approved = await client.post(f'/api/runs/{rid}/review',params={'project_id':pid},json={'action':'approve','comment':'Checked insufficiency.'})
        assert approved.status_code == 200,approved.text
        assert approved.json()['state'] == 'succeeded'
        assert len(await resources.research.list_reports(pid,tid)) == len(reports) == 1
        assert model.calls == 0
