import importlib
import json

import httpx
import pytest


def provider(client):
    try:
        m = importlib.import_module('researchflow.infrastructure.llm.embeddings')
    except ModuleNotFoundError:
        pytest.fail('embedding provider not implemented')
    return m.OpenAIEmbeddings(client, base_url='https://provider.test/v1', api_key='secret-test-key', model='embed-a', dimensions=2)


@pytest.mark.asyncio
async def test_embedding_orders_vectors_by_input_index_and_records_version():
    def response(request):
        body = json.loads(request.content)
        assert body['input'] == ['English', '中文'] and body['model'] == 'embed-a'
        return httpx.Response(200, json={'model': 'embed-a', 'data': [{'index': 1, 'embedding': [0.0, 1.0]}, {'index': 0, 'embedding': [1.0, 0.0]}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        batch = await provider(client).embed(('English', '中文'))
    assert batch.vectors == ((1.0, 0.0), (0.0, 1.0)) and batch.dimensions == 2 and batch.model == 'embed-a'


@pytest.mark.asyncio
@pytest.mark.parametrize('payload', [ {'model':'other','data':[{'index':0,'embedding':[1,0]}]}, {'model':'embed-a','data':[{'index':0,'embedding':[1]}]}, {'model':'embed-a','data':[{'index':0,'embedding':[True,0]}]}, {'model':'embed-a','data':[{'index':0,'embedding':[float('inf'),0]}]}, {'model':'embed-a','data':[]}, {'model':'embed-a','data':[{'index':0,'embedding':[0,0]}]} ], ids=['model-change','dimension-change','boolean','infinite','missing','zero'])
async def test_invalid_embedding_cannot_enter_vector_index(payload):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=json.dumps(payload), headers={'content-type':'application/json'}))) as client:
        with pytest.raises(ValueError, match='embedding_protocol'):
            await provider(client).embed(('text',))
