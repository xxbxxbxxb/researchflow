import importlib

import httpx
import pytest

from researchflow.settings import Settings


@pytest.mark.asyncio
async def test_embedding_configuration_is_connected_to_the_actual_adapter(monkeypatch):
    for key,value in {'RF_DATABASE_URL':'postgresql+psycopg://fixture','RF_EMBEDDING_BASE_URL':'https://provider.test/v1','RF_EMBEDDING_API_KEY':'secret-embedding-key','RF_EMBEDDING_MODEL':'fixture-embedding','RF_EMBEDDING_DIMENSIONS':'2'}.items():
        monkeypatch.setenv(key,value)
    settings=Settings.from_env()
    assert getattr(settings,'embedding_configured',False),'configured embeddings must not remain an unused adapter'
    composition=importlib.import_module('researchflow.composition')
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'model':'fixture-embedding','data':[{'index':0,'embedding':[1,0]}]}))) as client:
        provider=composition.configured_embeddings(settings,client)
        batch=await provider.embed(('source text',))
    assert batch.vectors==((1.0,0.0),)
    assert 'secret-embedding-key' not in repr(settings)
