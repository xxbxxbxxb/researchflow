import asyncio

import pytest

from test_task_api import authenticated_api
from test_project_knowledge import report


@pytest.mark.asyncio
async def test_follow_up_starts_only_after_explicit_action_and_is_atomic_idempotent(database,repository,tmp_path):
    result = await report(repository)
    async with authenticated_api(database,tmp_path) as (client,app):
        response = await client.post('/api/projects/p/follow-ups',json={'parent_task_id':'t','question':'Which condition should be tested next?','claim_ids':[result.claims[0].claim_id]})
        assert response.status_code==201,response.text
        draft = response.json()
        assert not await app.state.resources.runs.list_runs('p')
        endpoint = f'/api/projects/p/follow-ups/{draft["draft_id"]}/start'
        first,second = await asyncio.gather(client.post(endpoint,json={'mode':'demo'}),client.post(endpoint,json={'mode':'demo'}))
        assert first.status_code==second.status_code==201,(first.text,second.text)
        assert first.json()['run_id']==second.json()['run_id']
        task = await repository.get_task('p',first.json()['task_id'])
        assert task.parent_task_id=='t'
        assert len(await app.state.resources.runs.list_runs('p'))==1
        drafts = await app.state.resources.knowledge_repository.list_drafts('p')
        assert drafts[0].started_run_id==first.json()['run_id']
        changed = await client.post(endpoint,json={'mode':'demo','demo_case':'contradicted'})
        assert changed.status_code==409
