import importlib

import pytest

from researchflow.application.evidence import manual_evidence
from researchflow.domain.projects import Project, TaskRecord
from researchflow.domain.research import Evidence
from researchflow.infrastructure.llm.demo_model import CASES, DemoCaseModel
from researchflow.infrastructure.storage.retrieval import PostgresRetriever
from researchflow.infrastructure.storage.run_repository import RunRepository
from researchflow.runtime.fixed_workflow import FixedWorkflow


def module():
    try:
        return importlib.import_module('researchflow.runtime.graph_workflow')
    except ModuleNotFoundError:
        pytest.fail('LangGraph driver is not implemented')


@pytest.mark.asyncio
async def test_graph_and_fixed_have_same_evidence_verdicts_and_conclusions(database,repository):
    graph=module()
    await repository.create_project(Project('p','Parity'))
    snapshot,_=manual_evidence('p',Evidence('e','fixture','p1',CASES['supported']['source']))
    await repository.save_snapshot(snapshot)
    retriever=PostgresRetriever(database)
    await retriever.index_snapshot(snapshot)
    await repository.save_task(TaskRecord('t','p','synthetic sample size',(snapshot.snapshot_id,)))
    runs=RunRepository(database,repository)
    results=[]
    for version,driver in [('fixed-v1',FixedWorkflow),('graph-v1',graph.GraphWorkflow)]:
        await runs.enqueue('t','p',version,{'workflow_version':version,'execution_mode':'demo'})
        handle=await runs.claim_next('w')
        result=await driver(runs,repository,retriever,DemoCaseModel(),'demo').execute(handle)
        await runs.finish(handle,result.state)
        results.append(await repository.get_result('p',result.report_id))
    assert results[0].report.conclusion_claim_ids==results[1].report.conclusion_claim_ids
    assert [v.status for v in results[0].verifications]==[v.status for v in results[1].verifications]==['supported']


def test_checkpoint_serializer_refuses_pickle_and_arbitrary_objects():
    cp=importlib.import_module('researchflow.runtime.checkpointer') if importlib.util.find_spec('researchflow.runtime.checkpointer') else None
    assert cp is not None,'safe checkpoint serializer is missing'
    serde=cp.JSONSerializer()
    with pytest.raises(ValueError):
        serde.loads_typed(('pickle',b'cos\nsystem\n'))
    with pytest.raises((ValueError,TypeError)):
        serde.dumps_typed(object())

