import asyncio

import httpx
import pytest

from researchflow.infrastructure.llm.openai_compatible import (
    LLMProviderError,
    OpenAICompatibleConfig,
    OpenAICompatibleLLM
)
from researchflow.ports.llm import LLMRequest

def make_config() ->OpenAICompatibleConfig:
    return OpenAICompatibleConfig(
        base_url="https://llm.example/v1",
        api_key="test-key",
        model="test-model",
    )

def test_generate_maps_provider_response() ->None:
    async def handler(
        request:httpx.Request,
    ) ->httpx.Response:
        assert (
            str(request.url)
            == "https://llm.example/v1/chat/completions"
        )
        assert(
            request.headers["Authorization"]
            == "Bearer test-key"
        )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "grounded answer"
                        }
                    }
                ]
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

            response = await llm.generate(
                LLMRequest(prompt="question")
            )

            assert response.text == "grounded answer"

    asyncio.run(scenario())
def test_generate_translates_http_error() -> None:
    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            503,
            json={"error": "unavailable"},
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
                LLMProviderError,
                match="request failed",
            ):
                await llm.generate(
                    LLMRequest(prompt="question")
                )

    asyncio.run(scenario())