from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import Field

from researchflow.api.auth import require_principal, require_project
from researchflow.api.errors import APIError
from researchflow.api.runs import policy_version
from researchflow.api.schemas import KnowledgeRecordResponse, StrictInput
from researchflow.domain.access import Principal
from researchflow.domain.claims import Verification
from researchflow.domain.knowledge import FollowUpDraft, KnowledgeEntry
from researchflow.domain.runs import RunRecord
from researchflow.infrastructure.storage.codec import jsonable

router = APIRouter(prefix='/api/projects/{project_id}',tags=['knowledge'],dependencies=[Depends(require_project)])


class AcceptInput(StrictInput):
    verification_id: str = Field(min_length=1,max_length=200)


class OverrideInput(StrictInput):
    status: Literal['supported','contradicted','insufficient','inconclusive']
    reason: str = Field(min_length=1,max_length=2000)


class SupersedeInput(StrictInput):
    new_verification_id: str = Field(min_length=1,max_length=200)


class FollowUpInput(StrictInput):
    parent_task_id: str = Field(min_length=1,max_length=200)
    question: str = Field(min_length=1,max_length=5000)
    claim_ids: list[str] = Field(default_factory=list,max_length=12)


class FollowUpStart(StrictInput):
    mode: Literal['demo','live'] | None = None
    demo_case: Literal['supported','contradicted','insufficient','invalid-citation'] = 'supported'
    require_review: bool = False


@router.get('/knowledge',response_model=tuple[KnowledgeRecordResponse,...])
async def list_knowledge(project_id: str,request: Request):
    storage = request.app.state.resources.knowledge_repository
    records = []
    for entry in await storage.list_entries(project_id):
        context = await storage.verification_context(project_id,entry.verification_id)
        candidates = await storage.candidates(project_id,entry.knowledge_id) if entry.status=='active' else ()
        records.append({'entry':jsonable(entry),'claim':jsonable(context.claim),'verification':jsonable(context.verification),'evidences':jsonable(context.result.evidences),'replacement_candidates':jsonable(candidates)})
    return records


@router.post('/knowledge/accept',status_code=201,response_model=KnowledgeEntry)
async def accept(project_id: str,data: AcceptInput,request: Request,principal: Principal = Depends(require_principal)):
    return jsonable(await request.app.state.resources.knowledge.accept(project_id,data.verification_id,principal.actor_id))


@router.post('/verifications/{verification_id}/override',status_code=201,response_model=Verification)
async def override(project_id: str,verification_id: str,data: OverrideInput,request: Request,principal: Principal = Depends(require_principal)):
    return jsonable(await request.app.state.resources.knowledge.override(project_id,verification_id,data.status,data.reason,principal.actor_id))


@router.post('/knowledge/{knowledge_id}/supersede',status_code=201,response_model=KnowledgeEntry)
async def supersede(project_id: str,knowledge_id: str,data: SupersedeInput,request: Request,principal: Principal = Depends(require_principal)):
    return jsonable(await request.app.state.resources.knowledge.supersede(project_id,knowledge_id,data.new_verification_id,principal.actor_id))


@router.post('/follow-ups',status_code=201,response_model=FollowUpDraft)
async def draft(project_id: str,data: FollowUpInput,request: Request):
    return jsonable(await request.app.state.resources.knowledge.draft_follow_up(project_id,data.parent_task_id,data.question,tuple(data.claim_ids)))


@router.get('/follow-ups',response_model=tuple[FollowUpDraft,...])
async def drafts(project_id: str,request: Request):
    return jsonable(await request.app.state.resources.knowledge_repository.list_drafts(project_id))


@router.post('/follow-ups/{draft_id}/start',status_code=201,response_model=RunRecord)
async def start_draft(project_id: str,draft_id: str,data: FollowUpStart,request: Request):
    settings = request.app.state.settings
    mode = data.mode or settings.execution_mode
    if mode=='live' and not settings.live_configured:
        raise APIError(409,'configuration_missing','Live mode requires a configured model provider.')
    manifest = {'execution_mode':mode,'demo_case':data.demo_case,'require_review':data.require_review,'workflow_version':'fixed-v1','model_version':settings.llm_model if mode=='live' else 'demo:fixed-case-v1'}
    try:
        record = await request.app.state.resources.knowledge_repository.start_draft(project_id,draft_id,policy_version(settings,mode),manifest)
    except ValueError as exc:
        if str(exc)=='draft_start_conflict':
            raise APIError(409,'idempotency_conflict','This follow-up was already started with different inputs.') from exc
        raise
    return jsonable(record)
