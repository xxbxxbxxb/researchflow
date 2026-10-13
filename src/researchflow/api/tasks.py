from uuid import uuid4

from fastapi import APIRouter,Request,Depends

from researchflow.api.auth import require_project
from researchflow.api.schemas import TaskInput
from researchflow.domain.projects import TaskRecord
from researchflow.infrastructure.storage.codec import jsonable

router = APIRouter(prefix='/api/projects/{project_id}/tasks',tags=['tasks'],dependencies=[Depends(require_project)])


@router.get('',response_model=tuple[TaskRecord,...])
async def list_tasks(project_id: str,request: Request):
    return jsonable(await request.app.state.resources.research.list_tasks(project_id))


@router.post('',status_code=201,response_model=TaskRecord)
async def create_task(project_id: str,data: TaskInput,request: Request):
    task = TaskRecord(uuid4().hex,project_id,data.question,tuple(data.source_ids),data.parent_task_id)
    await request.app.state.resources.research.save_task(task)
    return jsonable(task)
