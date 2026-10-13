import importlib

import httpx
import pytest

from researchflow.infrastructure.llm.errors import (
    LLMProviderProtocolError,
    LLMProviderRateLimitError,
    LLMProviderRequestError,
    LLMProviderUnavailableError,
)
from researchflow.infrastructure.llm.openai_compatible import OpenAICompatibleConfig


def api():
    if importlib.util.find_spec('researchflow.infrastructure.llm.chat_model') is None:
        pytest.fail('Chat model adapter is not implemented')
    return importlib.import_module('researchflow.infrastructure.llm.chat_model'), importlib.import_module('researchflow.ports.model')


@pytest.mark.asyncio
async def test_chat_messages_tools_and_usage_cross_http_boundary():
    app, types = api()
    seen = []
    async def handler(request):
        import json
        seen.append(json.loads(request.content))
        return httpx.Response(200, headers={'x-request-id':'req1'}, json={'model':'actual-model','usage':{'prompt_tokens':7,'completion_tokens':3},'choices':[{'finish_reason':'tool_calls','message':{'content':None,'tool_calls':[{'id':'call1','type':'function','function':{'name':'search_project','arguments':'{"query":"abc"}'}}]}}]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        model = app.OpenAIChatModel(client, OpenAICompatibleConfig('https://example.org/v1','secret','model'))
        result = await model.complete(types.ChatRequest((types.ChatMessage('system','rules'),types.ChatMessage('user','data')),tools=({'type':'function','function':{'name':'search_project','parameters':{'type':'object'}}},)))
    assert seen[0]['messages'][0] == {'role':'system','content':'rules'}
    assert seen[0]['tools'][0]['function']['name'] == 'search_project'
    assert result.text == '' and result.tool_calls[0].arguments == {'query':'abc'}
    assert result.usage.input_tokens == 7 and result.usage.output_tokens == 3
    assert result.request_id == 'req1' and result.model == 'actual-model'


@pytest.mark.asyncio
@pytest.mark.parametrize('body', [{'choices':[]},{'choices':[{'message':{'content':None,'refusal':'no'}}]},{'choices':[{'message':{'content':'truncated'},'finish_reason':'length'}]}])
async def test_refused_or_incomplete_response_is_a_protocol_failure(body):
    app, types = api()
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _:httpx.Response(200,json=body))) as client:
        model = app.OpenAIChatModel(client, OpenAICompatibleConfig('https://example.org/v1','key','model'))
        with pytest.raises(LLMProviderProtocolError):
            await model.complete(types.ChatRequest((types.ChatMessage('user','q'),)))


@pytest.mark.asyncio
@pytest.mark.parametrize('code,error',[(401,LLMProviderRequestError),(429,LLMProviderRateLimitError),(503,LLMProviderUnavailableError)])
async def test_chat_preserves_provider_failure_taxonomy(code,error):
    app, types = api()
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _:httpx.Response(code))) as client:
        model=app.OpenAIChatModel(client,OpenAICompatibleConfig('https://example.org/v1','key','model'))
        with pytest.raises(error):
            await model.complete(types.ChatRequest((types.ChatMessage('user','q'),)))
