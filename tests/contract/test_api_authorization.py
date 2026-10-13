import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest


def api():
    try:
        return importlib.import_module('researchflow.api.app'),importlib.import_module('researchflow.settings')
    except ModuleNotFoundError:
        pytest.fail('authenticated API not implemented')


@pytest.mark.asyncio
async def test_anonymous_write_is_denied_before_repository_access():
    m,s = api()
    app = m.create_app(s.Settings(database_url='postgresql+psycopg://unused/unused'))
    runs = AsyncMock()
    app.state.resources = SimpleNamespace(runs=runs,sessions=AsyncMock())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://testserver') as client:
        response = await client.post('/api/tasks/t/runs',json={})
    assert response.status_code == 401
    runs.enqueue.assert_not_called()
    assert set(response.json()) == {'code','message','request_id','details'}


@pytest.mark.asyncio
async def test_body_limit_is_applied_before_any_unbounded_read():
    m,s = api()
    app = m.create_app(s.Settings(database_url='postgresql+psycopg://unused/unused'))
    received = 0
    async def content():
        nonlocal received
        for _ in range(30):
            received += 1
            yield b'x' * (1024 * 1024)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://testserver') as client:
        response = await client.post('/api/auth/login',content=content(),headers={'content-type':'application/json'})
    assert response.status_code == 413 and received <= 2


def test_settings_hide_credentials_and_protect_public_bind():
    m,s = api()
    settings = s.Settings(database_url='postgresql+psycopg://u:secret-test-key@host/db',password_hash=None,llm_api_key='secret-test-key')
    assert 'secret-test-key' not in repr(settings)
    with pytest.raises(ValueError,match='authentication'):
        settings.validate_binding('0.0.0.0')
    settings.validate_binding('127.0.0.1')
