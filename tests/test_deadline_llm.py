import asyncio

import pytest

from researchflow.infrastructure.llm.deadline_llm import (
    DeadlineLLM,
)
from researchflow.infrastructure.llm.errors import (
    LLMProviderRateLimitError,
)
from researchflow.infrastructure.llm.retry_llm import (
    RetryLLM,
)
from researchflow.ports.llm import (
    LLMRequest,
    LLMResponse,
)


class ImmediateLLM:
    async def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        return LLMResponse(text="success")


class BlockingLLM:
    def __init__(self) -> None:
        self.cancelled = False

    async def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        try:
            await asyncio.Event().wait()

        except asyncio.CancelledError:
            self.cancelled = True
            raise

        raise AssertionError("unreachable")


class RateLimitThenSuccessLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        self.calls += 1

        if self.calls == 1:
            raise LLMProviderRateLimitError(
                "rate limited",
                retry_after_seconds=5.0,
            )

        return LLMResponse(text="recovered")


def test_success_within_deadline() -> None:
    async def scenario() -> None:
        llm = DeadlineLLM(
            delegate=ImmediateLLM(),
            timeout_seconds=1.0,
        )

        response = await llm.generate(
            LLMRequest(prompt="question")
        )

        assert response.text == "success"

    asyncio.run(scenario())


def test_deadline_cancels_running_operation() -> None:
    async def scenario() -> None:
        delegate = BlockingLLM()

        llm = DeadlineLLM(
            delegate=delegate,
            timeout_seconds=0.05,
        )

        with pytest.raises(TimeoutError):
            await llm.generate(
                LLMRequest(prompt="question")
            )

        assert delegate.cancelled is True

    asyncio.run(scenario())


def test_deadline_covers_retry_after_wait() -> None:
    async def scenario() -> None:
        delegate = RateLimitThenSuccessLLM()

        retry_llm = RetryLLM(
            delegate=delegate,
            max_attempts=3,
            base_delay_seconds=0.5,
        )

        llm = DeadlineLLM(
            delegate=retry_llm,
            timeout_seconds=0.05,
        )

        with pytest.raises(TimeoutError):
            await llm.generate(
                LLMRequest(prompt="question")
            )

        assert delegate.calls == 1

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "timeout_seconds",
    [
        0.0,
        -1.0,
        float("inf"),
        float("nan"),
    ],
)
def test_rejects_invalid_timeout(
    timeout_seconds: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="positive finite number",
    ):
        DeadlineLLM(
            delegate=ImmediateLLM(),
            timeout_seconds=timeout_seconds,
        )