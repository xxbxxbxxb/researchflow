from typing import Literal
from fastapi import APIRouter,Depends,Request
from pydantic import Field

from researchflow.api.auth import require_project,require_principal
from researchflow.api.schemas import StrictInput
from researchflow.domain.access import Principal
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


@router.get('/knowledge')
async def list_knowledge(project_id: str,request: Request):
    storage = request.app.state.resources.knowledge_repository
    records = []
    for entry in await storage.list_entries(project_id):
        context = await storage.verification_context(project_id,entry.verification_id)
        candidates = await storage.candidates(project_id,entry.knowledge_id) if entry.status=='active' else ()
        records.append({'entry':jsonable(entry),'claim':jsonable(context.claim),'verification':jsonable(context.verification),'evidences':jsonable(context.result.evidences),'replacement_candidates':jsonable(candidates)})
    return records


@router.post('/knowledge/accept',status_code=201)
async def accept(project_id: str,data: AcceptInput,request: Request,principal: Principal = Depends(require_principal)):
    return jsonable(await request.app.state.resources.knowledge.accept(project_id,data.verification_id,principal.actor_id))


@router.post('/verifications/{verification_id}/override',status_code=201)
async def override(project_id: str,verification_id: str,data: OverrideInput,request: Request,principal: Principal = Depends(require_principal)):
    return jsonable(await request.app.state.resources.knowledge.override(project_id,verification_id,data.status,data.reason,principal.actor_id))


@router.post('/knowledge/{knowledge_id}/supersede',status_code=201)
async def supersede(project_id: str,knowledge_id: str,data: SupersedeInput,request: Request,principal: Principal = Depends(require_principal)):
    return jsonable(await request.app.state.resources.knowledge.supersede(project_id,knowledge_id,data.new_verification_id,principal.actor_id))


@router.post('/follow-ups',status_code=201)
async def draft(project_id: str,data: FollowUpInput,request: Request):
    return jsonable(await request.app.state.resources.knowledge.draft_follow_up(project_id,data.parent_task_id,data.question,tuple(data.claim_ids)))


@router.get('/follow-ups')
async def drafts(project_id: str,request: Request):
    return jsonable(await request.app.state.resources.knowledge_repository.list_drafts(project_id))
