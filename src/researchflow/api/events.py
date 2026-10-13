import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from researchflow.api.auth import require_project
from researchflow.api.errors import APIError
from researchflow.api.schemas import RunEventResponse

router = APIRouter(tags=['runs'],dependencies=[Depends(require_project)])


@router.get('/api/runs/{run_id}/event-history',response_model=tuple[RunEventResponse,...])
async def history(run_id: str,project_id: str,request: Request,after_id: int = 0):
    runs = request.app.state.resources.runs
    if await runs.get_run(project_id,run_id) is None:
        raise APIError(404,'not_found','Run was not found.')
    if after_id<0:
        raise APIError(400,'invalid_cursor','Cursor must be nonnegative.')
    return await runs.list_events(project_id,run_id,after_id)


async def event_stream(runs,project_id: str,run_id: str,after_id: int = 0,heartbeat_seconds: float = 15.0):
    cursor = after_id
    heartbeat_at = asyncio.get_running_loop().time()+heartbeat_seconds
    while True:
        events = await runs.list_events(project_id,run_id,cursor)
        for event in events:
            cursor = event['event_id']
            yield f'id: {cursor}\nevent: {event["kind"]}\ndata: {json.dumps(event,ensure_ascii=False)}\n\n'
        if len(events)==100:
            continue  # drain before examining the terminal status
        run = await runs.get_run(project_id,run_id)
        if run is None or run.state in {'succeeded','failed','cancelled'}:
            return
        now = asyncio.get_running_loop().time()
        if now >= heartbeat_at:
            yield ': heartbeat\n\n'
            heartbeat_at = now+heartbeat_seconds
        await asyncio.sleep(min(0.25,heartbeat_seconds))


@router.get('/api/runs/{run_id}/events')
async def subscribe(run_id: str,project_id: str,request: Request):
    runs = request.app.state.resources.runs
    if await runs.get_run(project_id,run_id) is None:
        raise APIError(404,'not_found','Run was not found.')
    cursor = request.headers.get('last-event-id',request.query_params.get('after_id','0'))
    try:
        after_id = int(cursor)
        if after_id<0:
            raise ValueError()
    except ValueError as exc:
        raise APIError(400,'invalid_cursor','Event cursor must be a nonnegative integer.') from exc
    return StreamingResponse(event_stream(runs,project_id,run_id,after_id),media_type='text/event-stream',headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})
