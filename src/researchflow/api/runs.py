import json
from hashlib import sha256

from fastapi import APIRouter, Depends, Header, Request

from researchflow.api.auth import require_principal, require_project
from researchflow.api.errors import APIError
from researchflow.api.schemas import ResumeInput, ReviewInput, RunMetricsResponse, RunStart
from researchflow.application.claims import CLAIM_PROMPT_VERSION
from researchflow.application.retrieval import INDEX_VERSION
from researchflow.domain.access import Principal
from researchflow.domain.runs import ReviewDecision, RunRecord
from researchflow.domain.usage import RunBudget
from researchflow.infrastructure.storage.codec import jsonable

router = APIRouter(tags=['runs'])


def policy_version(settings,mode: str,driver: str = 'fixed') -> str:
    from researchflow.runtime.policy import source_policy_hash
    policy = [driver+'-v1',mode,settings.llm_model if mode=='live' else 'demo:fixed-case-v1',CLAIM_PROMPT_VERSION,INDEX_VERSION,source_policy_hash(),settings.context_window if mode=='live' else None,settings.embedding_model if mode=='live' else None,settings.embedding_dimensions if mode=='live' else None]
    return sha256(json.dumps(policy,ensure_ascii=False).encode()).hexdigest()


@router.post('/api/tasks/{task_id}/runs',status_code=201,response_model=RunRecord)
async def start_run(task_id: str,data: RunStart,request: Request,principal: Principal = Depends(require_principal),idempotency_key: str | None = Header(default=None)):
    await require_project(request,data.project_id,principal)
    settings = request.app.state.settings
    mode = data.mode or settings.execution_mode
    if mode == 'live' and not settings.live_configured:
        raise APIError(409,'configuration_missing','Live mode requires a configured model provider. Select the explicit demo mode to run fixtures.')
    if data.collect_sources and mode=='demo':
        raise APIError(409,'demo_tools_disabled','External source collection requires an explicit live research run.')
    if not idempotency_key:
        raise APIError(400,'idempotency_key_required','Provide an Idempotency-Key to start research.')
    task = await request.app.state.resources.research.get_task(data.project_id,task_id)
    if task is None:
        raise APIError(404,'not_found','Task was not found in the project.')
    manifest = {'execution_mode':mode,'demo_case':data.demo_case,'model_version':settings.llm_model if mode=='live' else 'demo:fixed-case-v1','workflow_version':data.driver+'-v1','require_review':data.require_review,'collect_sources':data.collect_sources}
    payload = {**data.model_dump(),'mode':mode,'task_id':task_id,'actor_id':principal.actor_id}
    fingerprint = sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    try:
        record = await request.app.state.resources.runs.enqueue_idempotent(task_id,data.project_id,policy_version(settings,mode,data.driver),manifest,idempotency_key,fingerprint)
    except ValueError as exc:
        if str(exc)=='idempotency_conflict':
            raise APIError(409,'idempotency_conflict','This idempotency key was already used with different inputs.') from exc
        raise
    return jsonable(record)


@router.get('/api/runs/{run_id}',dependencies=[Depends(require_project)],response_model=RunRecord)
async def get_run(run_id: str,project_id: str,request: Request):
    record = await request.app.state.resources.runs.get_run(project_id,run_id)
    if record is None:
        raise APIError(404,'not_found','Run was not found.')
    return jsonable(record)


@router.get('/api/projects/{project_id}/runs',dependencies=[Depends(require_project)],response_model=tuple[RunRecord,...])
async def list_runs(project_id: str,request: Request,task_id: str | None = None):
    return jsonable(await request.app.state.resources.runs.list_runs(project_id,task_id))


@router.post('/api/runs/{run_id}/cancel',dependencies=[Depends(require_project)],response_model=RunRecord)
async def cancel(run_id: str,project_id: str,request: Request):
    return jsonable(await request.app.state.resources.runs.request_cancel(project_id,run_id))


@router.post('/api/runs/{run_id}/resume',dependencies=[Depends(require_project)],response_model=RunRecord)
async def resume(run_id: str,project_id: str,data: ResumeInput,request: Request):
    runs = request.app.state.resources.runs
    record = await runs.get_run(project_id,run_id)
    if record is None:
        raise APIError(404,'not_found','Run was not found.')
    mode = record.input_manifest['execution_mode']
    driver=record.input_manifest['workflow_version'].split('-')[0]
    version = policy_version(request.app.state.settings,mode,driver)
    if data.input_version and data.input_version != version:
        raise APIError(409,'input_version_mismatch','Current execution policy differs from the requested version.')
    return jsonable(await runs.resume(project_id,run_id,version))


@router.post('/api/runs/{run_id}/review',dependencies=[Depends(require_project)],response_model=RunRecord)
async def review(run_id: str,project_id: str,data: ReviewInput,request: Request,principal: Principal = Depends(require_principal)):
    return jsonable(await request.app.state.resources.runs.review(project_id,run_id,ReviewDecision(data.action,principal.actor_id,data.comment)))


@router.get('/api/runs/{run_id}/budget',dependencies=[Depends(require_project)],response_model=RunBudget | None)
async def budget_snapshot(run_id: str, project_id: str, request: Request):
    resources=request.app.state.resources
    if await resources.runs.get_run(project_id,run_id) is None:
        raise APIError(404,'not_found','Run was not found.')
    return await resources.budgets.read_snapshot(project_id,run_id)


@router.get('/api/runs/{run_id}/usage',dependencies=[Depends(require_project)])
async def usage_summary(run_id: str, project_id: str, request: Request):
    resources=request.app.state.resources
    if await resources.runs.get_run(project_id,run_id) is None:
        raise APIError(404,'not_found','Run was not found.')
    records=await resources.budgets.list_usage(project_id,run_id)
    costs=[record['estimated_cost'] for record in records]
    total=sum(costs) if costs and all(cost is not None for cost in costs) else None
    return {'attempts':records,'estimated_cost':total,'currency':'USD','usage_known':bool(records) and all(record['input_tokens'] is not None and record['output_tokens'] is not None for record in records)}


@router.get('/api/runs/{run_id}/metrics',dependencies=[Depends(require_project)],response_model=RunMetricsResponse)
async def run_metrics(run_id: str,project_id: str,request: Request):
    from researchflow.infrastructure.telemetry.metrics import execution_metrics
    resources=request.app.state.resources
    record=await resources.runs.get_run(project_id,run_id)
    if record is None:
        raise APIError(404,'not_found','Run was not found.')
    events=[]
    cursor=0
    while page:=await resources.runs.list_events(project_id,run_id,cursor):
        events.extend(page)
        cursor=page[-1]['event_id']
    usage=await resources.budgets.list_usage(project_id,run_id)
    metrics=execution_metrics(events,usage)
    reports=await resources.research.list_reports(project_id,record.task_id)
    latest=next((report for report in reports if report.run_id==run_id),None)
    distribution={status:0 for status in ('supported','contradicted','insufficient','inconclusive')}
    coverage=None
    if latest:
        result=await resources.research.get_result(project_id,latest.report_id)
        for verification in result.verifications:
            distribution[verification.status]+=1
        coverage=sum(bool(v.accepted_evidence_ids) for v in result.verifications)/len(result.verifications) if result.verifications else None
    return {**metrics,'verification_distribution':distribution,'citation_coverage':coverage}
