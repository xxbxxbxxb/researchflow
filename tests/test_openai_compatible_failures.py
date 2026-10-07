import asyncio

import httpx
import pytest

from researchflow.infrastructure.llm.errors import (
    LLMProviderProtocolError,
    LLMProviderRateLimitError,
    LLMProviderRequestError,
    LLMProviderUnavailableError,
)
from researchflow.infrastructure.llm.openai_compatible import (
    OpenAICompatibleConfig,
    OpenAICompatibleLLM,
)
from researchflow.ports.llm import LLMRequest
def make_config() ->OpenAICompatibleConfig:
    return OpenAICompatibleConfig(
        base_url="https://llm.example/v1",
        api_key="test-key",
        model="test-model"
    )
@pytest.mark.parametrize(
    ("status_code","expected_error"),
    [
        (400,LLMProviderRequestError),
        (401,LLMProviderRequestError),
        (429,LLMProviderRateLimitError),
        (500,LLMProviderUnavailableError),
        (503,LLMProviderUnavailableError),
    ],
)
def test_generate_classifies_http_failures(
    status_code: int,
    expected_error: type[Exception],
)->None:
    run_status_case(
        status_code,
        expected_error,
    )
def run_status_case(
    status_code: int,
    expected_error: type[Exception],
) -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            status_code,
            json={"error": "simulated"},
        )

    async def scenario() -> None:
        transport = httpx.MockTransport(handler)

        async with httpx.AsyncClient(
            transport=transport,
            timeout=5.0,
        ) as client:
            llm = OpenAICompatibleLLM(
                client=client,
                config=make_config(),
            )

            with pytest.raises(expected_error):
                await llm.generate(
                    LLMRequest(prompt="question")
                )

    asyncio.run(scenario())

    
def test_generate_classifies_timeout_as_unavailable() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        raise httpx.ReadTimeout(
            "simulated timeout",
            request=request,
        )

    async def scenario() -> None:
        transport = httpx.MockTransport(handler)

        async with httpx.AsyncClient(
            transport=transport,
            timeout=5.0,
        ) as client:
            llm = OpenAICompatibleLLM(
                client=client,
                config=make_config(),
            )

            with pytest.raises(
                LLMProviderUnavailableError
            ):
                await llm.generate(
                    LLMRequest(
                        prompt="question"
                    )
                )

    asyncio.run(scenario())
def test_generate_classifies_connect_timeout_as_unavailable() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        raise httpx.ConnectTimeout(
            "simulated connect timeout",
            request=request,
        )

    async def scenario() -> None:
        transport = httpx.MockTransport(handler)

        async with httpx.AsyncClient(
            transport=transport,
            timeout=5.0,
        ) as client:
            llm = OpenAICompatibleLLM(
                client=client,
                config=make_config(),
            )

            with pytest.raises(
                LLMProviderUnavailableError
            ):
                await llm.generate(
                    LLMRequest(
                        prompt="question"
                    )
                )

    asyncio.run(scenario())
def test_malformed_response_is_protocol_error() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "unexpected":"response"
            },
        )

    async def scenario() -> None:
        transport = httpx.MockTransport(handler)

        async with httpx.AsyncClient(
            transport=transport,
            timeout=5.0,
        ) as client:
            llm = OpenAICompatibleLLM(
                client=client,
                config=make_config(),
            )

            with pytest.raises(
                LLMProviderProtocolError
            ):
                await llm.generate(
                    LLMRequest(
                        prompt="question"
                    )
                )

    asyncio.run(scenario())
def test_rate_limit_preserves_retry_after() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            429,
            headers={
                "Retry-After": "5",
            },
            json={
                "error": "rate limited",
            },
        )

    async def scenario() -> None:
        transport = httpx.MockTransport(
            handler
        )

        async with httpx.AsyncClient(
            transport=transport,
            timeout=5.0,
        ) as client:
            llm = OpenAICompatibleLLM(
                client=client,
                config=make_config(),
            )

            with pytest.raises(
                LLMProviderRateLimitError
            ) as exc_info:
                await llm.generate(
                    LLMRequest(
                        prompt="question"
                    )
                )

            assert (
                exc_info.value.retry_after_seconds
                == 5.0
            )

    asyncio.run(scenario())
def test_rate_limit_invalid_retry_after() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            429,
            headers={
                "Retry-After": "invalid",
            },
            json={
                "error": "rate limited",
            },
        )

    async def scenario() -> None:
        transport = httpx.MockTransport(
            handler
        )

        async with httpx.AsyncClient(
            transport=transport,
            timeout=5.0,
        ) as client:
            llm = OpenAICompatibleLLM(
                client=client,
                config=make_config(),
            )

            with pytest.raises(
                LLMProviderRateLimitError
            ) as exc_info:
                await llm.generate(
                    LLMRequest(
                        prompt="question"
                    )
                )

            assert (
                exc_info.value.retry_after_seconds
                is None
            )

    asyncio.run(scenario())