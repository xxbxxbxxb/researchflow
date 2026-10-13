import importlib

import pytest
from test_task_api import authenticated_api


@pytest.mark.asyncio
async def test_event_reconnect_replays_only_missing_ids_without_cancelling(database,tmp_path):
    async with authenticated_api(database,tmp_path) as (client,app):
        pid = (await client.post('/api/projects',json={'name':'p'})).json()['project_id']
        tid = (await client.post(f'/api/projects/{pid}/tasks',json={'question':'evidence?'})).json()['task_id']
        rid = (await client.post(f'/api/tasks/{tid}/runs',json={'project_id':pid,'mode':'demo'},headers={'idempotency-key':'start'})).json()['run_id']
        runs = app.state.resources.runs
        events = await runs.list_events(pid,rid)
        first_id = events[0]['event_id']
        module = importlib.import_module('researchflow.api.events')
        stream = module.event_stream(runs,pid,rid,first_id,heartbeat_seconds=0.01)
        assert (await anext(stream)).startswith(': heartbeat')
        await stream.aclose()
        assert (await runs.get_run(pid,rid)).state == 'queued'
        await client.post(f'/api/runs/{rid}/cancel',params={'project_id':pid})
        response = await client.get(f'/api/runs/{rid}/events',params={'project_id':pid},headers={'last-event-id':str(first_id)})
        assert response.status_code == 200 and f'id: {first_id}\n' not in response.text
        frames = [frame for frame in response.text.split('\n\n') if frame.startswith('id:')]
        assert frames and all(int(frame.splitlines()[0][4:]) > first_id for frame in frames)
