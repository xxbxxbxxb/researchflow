from uuid import uuid4

from fastapi import APIRouter,Depends,Request

from researchflow.api.auth import require_principal
from researchflow.api.schemas import ProjectInput
from researchflow.domain.projects import Project
from researchflow.infrastructure.storage.codec import jsonable

router = APIRouter(prefix='/api/projects',tags=['projects'],dependencies=[Depends(require_principal)])


@router.get('')
async def list_projects(request: Request):
    return jsonable(await request.app.state.resources.research.list_projects())


@router.post('',status_code=201)
async def create_project(data: ProjectInput,request: Request):
    return jsonable(await request.app.state.resources.research.create_project(Project(uuid4().hex,data.name,data.background)))
