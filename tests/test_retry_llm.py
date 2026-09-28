import asyncio
import pytest

from researchflow.infrastructure.llm.errors import(
    LLMProviderProtocolError,
    LLMProviderRequestError,
    LLMProviderUnavailableError,
)
from researchflow.infrastructure.llm.retry_llm import(
    RetryLLM,
)
from researchflow.ports.llm import(
    LLMRequest,
    LLMResponse,
)

class SequencedLLM:
    def __init__(
        self,
        outcomes: list[
            LLMResponse | Exception
        ],
    ) ->None:
        self._outcomes = outcomes
        self.calls = 0
    async def generate(
        self,
        request: LLMRequest,
    ) ->LLMResponse:
        outcome = self._outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome,Exception):
            raise outcome
        return outcome

def test_retries_unavailable_error_then_succeeds() ->None:
    async def scenario() ->None:
        delegate = SequencedLLM(
            [
                LLMProviderUnavailableError(
                    "temporary failure"
                ),
                LLMResponse(text="recovered"),
            ]
        )
        llm = RetryLLM(
            delegate = delegate,
            max_attempts = 3,
        )
        response = await llm.generate(
            LLMRequest(prompt="question")
        )
        assert response.text == "recovered"
        assert delegate.calls == 2
    asyncio.run(scenario())
def test_stops_after_max_attempts() -> None:
    async def scenario() ->None:
        delegate = SequencedLLM(
            [
                LLMProviderUnavailableError(
                    "failure 1"
                ),
                LLMProviderUnavailableError(
                    "failure 2"
                ),
                LLMProviderUnavailableError(
                    "failure 3"
                ),
            ]
        )
        llm = RetryLLM(
            delegate = delegate,
            max_attempts = 3,
        )
        with pytest.raises(
            LLMProviderUnavailableError
        ):
            await llm.generate(
                LLMRequest(prompt="question")
        )
        assert delegate.calls == 3
    asyncio.run(scenario())
def test_does_not_retry_request_error() -> None:
    async def scenario() ->None:
        delegate = SequencedLLM(
            [
                LLMProviderRequestError(
                    "invalid request"
                )
            ]
        )
        llm = RetryLLM(
            delegate = delegate,
            max_attempts = 3,
        )
        with pytest.raises(
            LLMProviderRequestError
        ):
            await llm.generate(
                LLMRequest(prompt="question")
        )
        assert delegate.calls == 1
    asyncio.run(scenario())
def test_does_not_retry_protocol_error() -> None:
    async def scenario() ->None:
        delegate = SequencedLLM(
            [
                LLMProviderProtocolError(
                    "invalid payload"
                )
            ]
        )
        llm = RetryLLM(
            delegate = delegate,
            max_attempts = 3,
        )
        with pytest.raises(
            LLMProviderProtocolError
        ):
            await llm.generate(
                LLMRequest(prompt="question")
        )
        assert delegate.calls == 1
    asyncio.run(scenario())