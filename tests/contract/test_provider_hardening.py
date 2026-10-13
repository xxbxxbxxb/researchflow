import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from researchflow.infrastructure.llm.errors import LLMProviderRateLimitError
from researchflow.infrastructure.llm.openai_compatible import OpenAICompatibleConfig, OpenAICompatibleLLM
from researchflow.infrastructure.llm.retry_llm import RetryLLM
from researchflow.ports.llm import LLMRequest


@pytest.mark.parametrize('delay', [float('nan'), float('inf'), float('-inf')])
def test_retry_rejects_nonfinite_delay(delay):
    with pytest.raises(ValueError):
        RetryLLM(delegate=object(), base_delay_seconds=delay)


def test_config_repr_redacts_key():
    config = OpenAICompatibleConfig('https://example.org/v1', 'secret-test-key', 'model')
    assert 'secret-test-key' not in repr(config)


def test_retry_after_http_date():
    async def scenario():
        async def handler(request):
            return httpx.Response(429, headers={'Retry-After': 'Wed, 21 Oct 2015 07:28:00 GMT'})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            llm = OpenAICompatibleLLM(client, OpenAICompatibleConfig('https://example.org/v1', 'key', 'model'), clock=lambda: datetime(2015, 10, 21, 7, 27, 58, tzinfo=UTC))
            with pytest.raises(LLMProviderRateLimitError) as exc:
                await llm.generate(LLMRequest('question'))
            assert exc.value.retry_after_seconds == 2.0
    asyncio.run(scenario())


@pytest.mark.parametrize('value', ['inf', 'NaN', '-1', 'garbage'])
def test_retry_after_rejects_invalid_values(value):
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(429, headers={'Retry-After': value}))) as client:
            llm = OpenAICompatibleLLM(client, OpenAICompatibleConfig('https://example.org/v1', 'key', 'model'))
            with pytest.raises(LLMProviderRateLimitError) as exc:
                await llm.generate(LLMRequest('question'))
            assert exc.value.retry_after_seconds is None
    asyncio.run(scenario())


def test_external_cancel_does_not_retry():
    async def scenario():
        started = asyncio.Event()
        class Blocking:
            calls = 0
            async def generate(self, request):
                self.calls += 1
                started.set()
                await asyncio.Event().wait()
        provider = Blocking()
        task = asyncio.create_task(RetryLLM(provider).generate(LLMRequest('question')))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert provider.calls == 1
    asyncio.run(scenario())
