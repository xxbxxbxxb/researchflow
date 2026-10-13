from fastapi import APIRouter,Request,Depends

from researchflow.api.auth import require_project
from researchflow.api.errors import APIError
from researchflow.infrastructure.storage.codec import jsonable

router = APIRouter(tags=['reports'],dependencies=[Depends(require_project)])


@router.get('/api/projects/{project_id}/reports')
async def list_reports(project_id: str,request: Request,task_id: str | None = None):
    return jsonable(await request.app.state.resources.research.list_reports(project_id,task_id))


@router.get('/api/reports/{report_id}')
async def get_report(report_id: str,project_id: str,request: Request):
    return jsonable(await request.app.state.resources.research.get_result(project_id,report_id))


@router.get('/api/evidence/{evidence_id}')
async def get_evidence(evidence_id: str,project_id: str,request: Request):
    resources = request.app.state.resources
    evidence = await resources.research.get_evidence(project_id,evidence_id)
    if evidence is None:
        raise APIError(404,'not_found','Evidence was not found.')
    snapshot = await resources.research.get_snapshot(project_id,evidence.anchor.snapshot_id)
    if snapshot is None:
        raise APIError(404,'not_found','Original snapshot was not found.')
    return {'evidence':jsonable(evidence),'snapshot':jsonable(snapshot)}
