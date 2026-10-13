import importlib
from contextlib import asynccontextmanager

import httpx
import pytest
from argon2 import PasswordHasher


@asynccontextmanager
async def authenticated_api(database,tmp_path):
    try:
        api = importlib.import_module('researchflow.api.app')
        settings = importlib.import_module('researchflow.settings')
    except ModuleNotFoundError:
        pytest.fail('task API not implemented')
    config = settings.Settings(database_url=database.url,password_hash=PasswordHasher().hash('test-password'),allowed_origins=('http://testserver',),blob_root=tmp_path/'blobs',execution_mode='demo',secure_cookies=False)
    app = api.create_app(config,database=database)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://testserver',headers={'origin':'http://testserver'}) as client:
            login = await client.post('/api/auth/login',json={'password':'test-password'})
            assert login.status_code == 200,login.text
            client.headers['x-csrf-token'] = login.json()['csrf_token']
            yield client,app


@pytest.mark.asyncio
async def test_cookie_origin_csrf_and_atomic_run_idempotency(database,tmp_path):
    async with authenticated_api(database,tmp_path) as (client,app):
        assert client.cookies.get('rf_session')
        login = await client.post('/api/auth/login',json={'password':'test-password'})
        cookies = login.headers.get_list('set-cookie')
        assert any('HttpOnly' in cookie and 'SameSite=lax' in cookie for cookie in cookies)
        client.headers['x-csrf-token'] = login.json()['csrf_token']
        project = (await client.post('/api/projects',json={'name':'Project','background':'Research'})).json()
        pid = project['project_id']
        task = (await client.post(f'/api/projects/{pid}/tasks',json={'question':'What evidence is available?','source_ids':[]})).json()
        endpoint = f'/api/tasks/{task["task_id"]}/runs'
        body = {'project_id':pid,'mode':'demo'}
        denied = await client.post(endpoint,json=body,headers={'origin':'https://evil.test','idempotency-key':'x'})
        assert denied.status_code == 403
        denied = await client.post(endpoint,json=body,headers={'x-csrf-token':'wrong','idempotency-key':'x'})
        assert denied.status_code == 403
        first = await client.post(endpoint,json=body,headers={'idempotency-key':'one'})
        duplicate = await client.post(endpoint,json=body,headers={'idempotency-key':'one'})
        assert first.status_code == duplicate.status_code == 201,(first.text,duplicate.text)
        assert first.json()['run_id'] == duplicate.json()['run_id']
        assert len(await app.state.resources.runs.list_runs(pid)) == 1
        changed = await client.post(endpoint,json={**body,'demo_case':'contradicted'},headers={'idempotency-key':'one'})
        assert changed.status_code == 409
        assert len(await app.state.resources.runs.list_runs(pid)) == 1


@pytest.mark.asyncio
async def test_question_boundary_upload_and_missing_live_configuration(database,tmp_path):
    async with authenticated_api(database,tmp_path) as (client,app):
        project = (await client.post('/api/projects',json={'name':'p'})).json()['project_id']
        endpoint = f'/api/projects/{project}/tasks'
        assert (await client.post(endpoint,json={'question':'q'*5000})).status_code == 201
        assert (await client.post(endpoint,json={'question':'q'*5001})).status_code == 422
        uploaded = await client.post(f'/api/projects/{project}/sources',files={'file':('../../outside.md','中文实验样本为十二个。'.encode(),'text/markdown')})
        assert uploaded.status_code == 201,uploaded.text
        source = uploaded.json()
        assert source['pages'][0]['text'] == '中文实验样本为十二个。'
        task = (await client.post(endpoint,json={'question':'中文实验样本','source_ids':[source['snapshot_id']]})).json()
        missing = await client.post(f'/api/tasks/{task["task_id"]}/runs',json={'project_id':project,'mode':'live'},headers={'idempotency-key':'live'})
        assert missing.status_code == 409 and missing.json()['code'] == 'configuration_missing'
        assert not await app.state.resources.runs.list_runs(project)


@pytest.mark.asyncio
async def test_login_failures_are_rate_limited_in_database(database,tmp_path):
    async with authenticated_api(database,tmp_path) as (client,app):
        client.cookies.clear()
        for _ in range(5):
            response = await client.post('/api/auth/login',json={'password':'incorrect'},headers={'x-forwarded-for':'some-new-ip'})
            assert response.status_code == 401
        limited = await client.post('/api/auth/login',json={'password':'test-password'})
        assert limited.status_code == 429
