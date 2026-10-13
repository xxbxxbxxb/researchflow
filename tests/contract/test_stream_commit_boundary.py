import importlib
import asyncio
import pytest
import httpx

from researchflow.domain.runs import RunHandle
from researchflow.ports.model import ChatRequest,ChatMessage
from researchflow.runtime.model_runtime import ModelRuntime
from researchflow.runtime.budget import MemoryBudgetRepository
from researchflow.infrastructure.llm.errors import LLMProviderUnavailableError


def modules():
    try:
        stream=importlib.import_module('researchflow.runtime.streaming')
        ports=importlib.import_module('researchflow.ports.model')
        return stream,ports.ModelDelta
    except (ModuleNotFoundError,AttributeError):
        pytest.fail('stream delivery boundary is not implemented')


REQUEST=ChatRequest((ChatMessage('user','preview'),))
HANDLE=RunHandle('r','p','t',1,'w')


@pytest.mark.asyncio
@pytest.mark.parametrize('delivered',[False,True])
async def test_retry_is_allowed_only_before_first_user_visible_delta(delivered):
    stream,Delta=modules()
    class Provider:
        calls=0
        async def stream(self,request):
            self.calls+=1
            if self.calls==1:
                yield Delta('text','已交付内容' if delivered else '')
                raise LLMProviderUnavailableError('connection lost')
            yield Delta('text','完整的新内容')
            yield Delta('done')
    provider=Provider()
    budgets=MemoryBudgetRepository(HANDLE)
    runtime=ModelRuntime(provider,budgets,65536,random=lambda high:0)
    iterator=runtime.stream(HANDLE,REQUEST)
    first=await anext(iterator)
    if delivered:
        assert first.text=='已交付内容'
        with pytest.raises(stream.StreamInterruptedError):
            await anext(iterator)
        assert provider.calls==1
    else:
        assert first.text=='完整的新内容'
        assert [d.kind async for d in iterator]==['done']
        assert provider.calls==2


@pytest.mark.asyncio
async def test_missing_done_is_incomplete_and_closing_preview_closes_upstream_only():
    stream,Delta=modules()
    class Provider:
        closed=False
        async def stream(self,request):
            try:
                yield Delta('text','unverified')
                await asyncio.Future()
            finally:
                self.closed=True
    provider=Provider()
    budgets=MemoryBudgetRepository(HANDLE)
    runtime=ModelRuntime(provider,budgets,65536)
    iterator=runtime.stream(HANDLE,REQUEST)
    assert (await anext(iterator)).text=='unverified'
    await iterator.aclose()
    assert provider.closed and not budgets.slots
    assert budgets.budget.model_calls_used==1


@pytest.mark.asyncio
async def test_actual_http_sse_preserves_utf8_and_requires_terminal_done():
    stream,Delta=modules()
    adapter=importlib.import_module('researchflow.infrastructure.llm.streaming')
    from researchflow.infrastructure.llm.openai_compatible import OpenAICompatibleConfig
    class Bytes(httpx.AsyncByteStream):
        closed=False
        async def __aiter__(self):
            payload='data: {"choices":[{"delta":{"content":"中文"}}]}\n\ndata: [DONE]\n\n'.encode()
            for byte in payload:
                yield bytes([byte])
        async def aclose(self):
            self.closed=True
    body=Bytes()
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req:httpx.Response(200,stream=body))) as client:
        provider=adapter.OpenAIStreamModel(client,OpenAICompatibleConfig('https://provider.test','secret-key','fixture'))
        deltas=[d async for d in provider.stream(REQUEST)]
        assert [d.text for d in deltas if d.kind=='text']==['中文']
        assert deltas[-1].kind=='done'
        assert not client.is_closed and body.closed


@pytest.mark.asyncio
async def test_stream_without_terminal_done_cannot_be_completed():
    stream,Delta=modules()
    class Provider:
        calls=0
        async def stream(self,request):
            self.calls+=1
            yield Delta('text','partial')
    provider=Provider()
    runtime=ModelRuntime(provider,MemoryBudgetRepository(HANDLE),65536)
    with pytest.raises(stream.StreamInterruptedError):
        _=[d async for d in runtime.stream(HANDLE,REQUEST)]
    assert provider.calls==1
