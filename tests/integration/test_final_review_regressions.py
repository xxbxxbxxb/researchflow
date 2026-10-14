import json
from dataclasses import asdict, replace

import pytest

from researchflow.application.evidence import manual_evidence
from researchflow.domain.projects import Project, TaskRecord
from researchflow.domain.research import Evidence
from researchflow.domain.usage import BudgetExceededError, RunLimits
from researchflow.infrastructure.llm.demo_model import CASES, DemoCaseModel
from researchflow.infrastructure.storage.budget_repository import BudgetRepository
from researchflow.infrastructure.storage.retrieval import PostgresRetriever
from researchflow.infrastructure.storage.run_repository import RunRepository
from researchflow.ports.retrieval import EmbeddingBatch
from researchflow.runtime.fixed_workflow import FixedWorkflow


@pytest.mark.asyncio
async def test_demo_with_existing_vectors_never_sends_a_live_embedding_query(database,repository):
    # Break caught: substituting demo chat while retaining raw live query embeddings.
    from researchflow.composition import ConfiguredWorkflow
    await repository.create_project(Project('p','Explicit offline demonstration'))
    snapshot,_=manual_evidence('p',Evidence('e','synthetic','p1',CASES['supported']['source']))
    await repository.save_snapshot(snapshot)

    class IndexFixture:
        model='fixture-vectors'
        dimensions=2
        async def embed(self,texts):
            return EmbeddingBatch(tuple((1.0,0.1) for _ in texts),self.model,self.dimensions)

    await PostgresRetriever(database,IndexFixture()).index_snapshot(snapshot)

    class ForbiddenLiveEmbedding(IndexFixture):
        async def embed(self,texts):
            pytest.fail('explicit demo leaked its question to the live embedding provider')

    class ForbiddenLiveChat:
        async def complete(self,request):
            pytest.fail('explicit demo called the live chat provider')

    await repository.save_task(TaskRecord('t','p','synthetic sample size',(snapshot.snapshot_id,)))
    runs=RunRepository(database,repository)
    record=await runs.enqueue('t','p','fixed-v1',{'execution_mode':'demo','demo_case':'supported'})
    handle=await runs.claim_next('live-capable-worker')
    workflow=ConfiguredWorkflow(runs,repository,PostgresRetriever(database,ForbiddenLiveEmbedding()),ForbiddenLiveChat(),'live',context_window=65536)
    outcome=await workflow.execute(handle)
    result=await repository.get_result('p',outcome.report_id)
    assert result.report.execution_mode == 'demo'
    assert result.report.retrieval_mode == 'lexical'
    usage=await BudgetRepository(database,runs).list_usage('p',record.run_id)
    assert len(usage) == 2
    assert {row['operation'] for row in usage} == {'claims','verify'}


@pytest.mark.asyncio
@pytest.mark.parametrize('preview_first',[True,False])
async def test_first_budget_creator_cannot_replace_frozen_requested_limits(database,repository,preview_first):
    # Break caught: caller defaults win the first INSERT instead of the immutable manifest.
    await repository.create_project(Project('p','Shared immutable budget'))
    await repository.save_task(TaskRecord('t','p','no sources'))
    requested=RunLimits(max_steps=3,max_tool_calls=4,max_model_calls=1,max_concurrency=1,active_timeout_seconds=45,operation_timeout_seconds=7)
    runs=RunRepository(database,repository)
    await runs.enqueue('t','p','fixed-v1',{'execution_mode':'demo','limits':asdict(requested)})
    handle=await runs.claim_next('worker')
    preview=BudgetRepository(database,runs)
    worker=BudgetRepository(database,runs,requested)
    first,second=(preview,worker) if preview_first else (worker,preview)
    assert (await first.ensure(handle)).limits == requested
    assert (await second.ensure(handle)).limits == requested
    await first.reserve(handle,'model')
    with pytest.raises(BudgetExceededError):
        await second.reserve(handle,'model')
    assert (await second.snapshot(handle)).model_calls_used == 1


@pytest.mark.asyncio
async def test_superseded_contradiction_reaches_actual_claim_input_with_anchored_provenance(database,repository):
    # Break caught: rendering active knowledge as positive claim text without its verdict.
    from test_project_knowledge import report, service
    result=await report(repository)
    knowledge,port=service(repository,database)
    old=result.verifications[0]
    accepted=await knowledge.accept('p',old.verification_id,'owner')
    reason='A later human review found the experimental condition incompatible.'
    opposite=await knowledge.override('p',old.verification_id,'contradicted',reason,'owner')
    replacement=await knowledge.supersede('p',accepted.knowledge_id,opposite.verification_id,'owner')
    source_id=result.evidences[0].anchor.snapshot_id
    await repository.save_task(TaskRecord('next','p','synthetic sample size',(source_id,)))
    runs=RunRepository(database,repository)
    await runs.enqueue('next','p','fixed-v1',{'execution_mode':'demo'})
    handle=await runs.claim_next('worker')
    retriever=PostgresRetriever(database)
    await retriever.index_snapshot(await repository.get_snapshot('p',source_id))
    captured=[]

    class CaptureClaimInput(DemoCaseModel):
        async def complete(self,request):
            if request.operation=='claims':
                captured.append(json.loads(request.messages[-1].content))
            return await super().complete(request)

    workflow=FixedWorkflow(runs,repository,retriever,CaptureClaimInput(),'demo',knowledge=port)
    for phase in ('collect','retrieve','evidence','claims'):
        await workflow.step(handle,phase)
    context=captured[0]['project_knowledge']
    assert len(context) == 1
    item=context[0]
    assert item['knowledge_id'] == replacement.knowledge_id
    assert item['verification_status'] == 'contradicted'
    assert item['rationale'] == reason
    assert item['accepted_evidence_ids'] == ['e1']
    assert item['evidence'][0]['snapshot_id'] == source_id
    assert item['evidence'][0]['quote'] == result.evidences[0].evidence.text
    assert item['evidence'][0]['quote_hash'] == result.evidences[0].quote_hash


@pytest.mark.asyncio
async def test_unaccepted_evidence_in_old_report_cannot_make_knowledge_eligible(database,repository):
    # Break caught: choosing knowledge from any old report evidence, not accepted references.
    from test_project_knowledge import report, service
    result=await report(repository)
    unrelated,extra=manual_evidence('p',Evidence('unaccepted','other-paper','p1','Unrelated scoped material.'))
    await repository.save_snapshot(unrelated)
    copy=replace(result,report=replace(result.report,report_id='expanded-report'),evidences=(*result.evidences,extra))
    await repository.save_result(copy)
    knowledge,port=service(repository,database)
    await knowledge.accept('p',result.verifications[0].verification_id,'owner')
    await repository.save_task(TaskRecord('next','p','Unrelated scoped material',(unrelated.snapshot_id,)))
    runs=RunRepository(database,repository)
    await runs.enqueue('next','p','fixed-v1',{'execution_mode':'demo'})
    handle=await runs.claim_next('worker')
    workflow=FixedWorkflow(runs,repository,PostgresRetriever(database),DemoCaseModel(),'demo',knowledge=port)
    collected=await workflow.step(handle,'collect')
    assert collected.data['project_knowledge'] == []
