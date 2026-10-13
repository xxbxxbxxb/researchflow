from fastapi import APIRouter,Request,Depends
from fastapi.responses import Response
from starlette.datastructures import UploadFile

from researchflow.api.auth import require_project
from researchflow.api.errors import APIError
from researchflow.api.schemas import URLInput
from researchflow.ports.sources import SourceInput
from researchflow.infrastructure.storage.codec import jsonable

router = APIRouter(prefix='/api/projects/{project_id}/sources',tags=['sources'],dependencies=[Depends(require_project)])
MAX_BYTES = 20 * 1024 * 1024


@router.get('')
async def list_sources(project_id: str,request: Request):
    return jsonable(await request.app.state.resources.research.list_snapshots(project_id))


@router.post('',status_code=201)
async def import_source(project_id: str,request: Request):
    if request.headers.get('content-type','').lower().startswith('multipart/form-data'):
        async with request.form(max_files=1,max_fields=0,max_part_size=MAX_BYTES) as form:
            file = form.get('file')
            if not isinstance(file,UploadFile):
                raise APIError(422,'invalid_input','Upload a file using the file field.')
            data = bytearray()
            while chunk := await file.read(65536):
                data.extend(chunk)
                if len(data)>MAX_BYTES:
                    raise APIError(413,'payload_too_large','File exceeds 20 MiB.')
            source = SourceInput(filename=file.filename or 'upload',data=bytes(data),media_type=file.content_type or 'application/octet-stream')
    else:
        input_data = URLInput.model_validate(await request.json())
        source = SourceInput(url=input_data.url)
    resources = request.app.state.resources
    snapshot = await resources.ingestion.execute(project_id,source)
    await resources.retriever.index_snapshot(snapshot)
    return jsonable(snapshot)


@router.get('/{snapshot_id}')
async def get_snapshot(project_id: str,snapshot_id: str,request: Request):
    snapshot = await request.app.state.resources.research.get_snapshot(project_id,snapshot_id)
    if snapshot is None:
        raise APIError(404,'not_found','Source snapshot was not found.')
    return jsonable(snapshot)


@router.get('/{snapshot_id}/original')
async def get_original(project_id: str,snapshot_id: str,request: Request):
    resources = request.app.state.resources
    snapshot = await resources.research.get_snapshot(project_id,snapshot_id)
    if snapshot is None:
        raise APIError(404,'not_found','Source snapshot was not found.')
    try:
        data = resources.blobs.get(snapshot.content_hash)
    except FileNotFoundError as exc:
        raise APIError(404,'original_unavailable','Original bytes were not supplied for this snapshot.') from exc
    # Downloading original untrusted HTML never renders it in the application origin.
    return Response(data,media_type='application/octet-stream',headers={'Content-Disposition':'attachment; filename="source.bin"','X-Content-Type-Options':'nosniff','Content-Security-Policy':'sandbox'})
