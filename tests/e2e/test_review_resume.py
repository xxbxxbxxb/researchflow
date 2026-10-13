import importlib
import pytest
from researchflow.domain.projects import Project,TaskRecord
from researchflow.domain.runs import ReviewDecision
from researchflow.infrastructure.storage.run_repository import RunRepository
from researchflow.infrastructure.storage.retrieval import PostgresRetriever
from researchflow.infrastructure.storage.budget_repository import BudgetRepository
from researchflow.infrastructure.llm.demo_model import DemoCaseModel


@pytest.mark.asyncio
async def test_graph_review_restores_same_run_and_excludes_waiting_time(database,repository):
    try:
        graph=importlib.import_module('researchflow.runtime.graph_workflow')
    except ModuleNotFoundError:
        pytest.fail('persistent graph review is missing')
    await repository.create_project(Project('p','Human review'))
    await repository.save_task(TaskRecord('t','p','question'))
    runs=RunRepository(database,repository)
    record=await runs.enqueue('t','p','graph-v1',{'workflow_version':'graph-v1','execution_mode':'demo','require_review':True})
    handle=await runs.claim_next('before-review')
    budgets=BudgetRepository(database,runs)
    await budgets.ensure(handle)
    driver=graph.GraphWorkflow(runs,repository,PostgresRetriever(database),DemoCaseModel('insufficient'),'demo')
    outcome=await driver.execute(handle)
    assert outcome.state=='awaiting_review'
    await runs.finish(handle,outcome.state)
    before=await budgets.read_snapshot('p',record.run_id)
    await runs.review('p',record.run_id,ReviewDecision('approve','owner'))
    # A new saver and ownership epoch simulate a separate service lifetime.
    fresh=await runs.claim_next('after-review')
    after_wait=await budgets.read_snapshot('p',record.run_id)
    assert after_wait.active_elapsed_seconds==before.active_elapsed_seconds
    resumed=await graph.GraphWorkflow(runs,repository,PostgresRetriever(database),DemoCaseModel('insufficient'),'demo').execute(fresh)
    assert resumed.state=='succeeded' and resumed.report_id==outcome.report_id
    await runs.finish(fresh,resumed.state)
    assert len(await repository.list_reports('p','t'))==1
