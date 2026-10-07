import asyncio
import pytest

from researchflow.infrastructure.llm.errors import (
    LLMProviderRateLimitError,
    LLMProviderProtocolError,
    LLMProviderRequestError,
    LLMProviderUnavailableError,
)
from researchflow.infrastructure.llm.retry_llm import (
    RetryLLM,
)
from researchflow.ports.llm import (
    LLMRequest,
    LLMResponse,
)


class SequencedLLM:
    def __init__(
        self,
        outcomes: list[LLMResponse | Exception],
    ) -> None:
        self._outcomes = outcomes
        self.calls = 0

    async def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        outcome = self._outcomes[self.calls]
        self.calls += 1
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class RecordingSleeper:
    def __init__(self) -> None:
        self.delays: list[float] = []

    async def __call__(
        self,
        delay: float,
    ) -> None:
        self.delays.append(delay)


def test_retries_unavailable_error_then_succeeds() -> None:
    async def scenario() -> None:
        delegate = SequencedLLM(
            [
                LLMProviderUnavailableError("temporary failure"),
                LLMResponse(text="recovered"),
            ]
        )
        llm = RetryLLM(
            delegate=delegate,
            max_attempts=3,
            base_delay_seconds=0,
        )
        response = await llm.generate(LLMRequest(prompt="question"))
        assert response.text == "recovered"
        assert delegate.calls == 2

    asyncio.run(scenario())


def test_stops_after_max_attempts() -> None:
    async def scenario() -> None:
        delegate = SequencedLLM(
            [
                LLMProviderUnavailableError("failure 1"),
                LLMProviderUnavailableError("failure 2"),
                LLMProviderUnavailableError("failure 3"),
            ]
        )
        llm = RetryLLM(
            delegate=delegate,
            max_attempts=3,
            base_delay_seconds=0,
        )
        with pytest.raises(LLMProviderUnavailableError):
            await llm.generate(LLMRequest(prompt="question"))
        assert delegate.calls == 3

    asyncio.run(scenario())


def test_does_not_retry_request_error() -> None:
    async def scenario() -> None:
        delegate = SequencedLLM([LLMProviderRequestError("invalid request")])
        llm = RetryLLM(
            delegate=delegate,
            max_attempts=3,
        )
        with pytest.raises(LLMProviderRequestError):
            await llm.generate(LLMRequest(prompt="question"))
        assert delegate.calls == 1

    asyncio.run(scenario())


def test_does_not_retry_protocol_error() -> None:
    async def scenario() -> None:
        delegate = SequencedLLM([LLMProviderProtocolError("invalid payload")])
        llm = RetryLLM(
            delegate=delegate,
            max_attempts=3,
        )
        with pytest.raises(LLMProviderProtocolError):
            await llm.generate(LLMRequest(prompt="question"))
        assert delegate.calls == 1

    asyncio.run(scenario())


def test_retries_rate_limit_error_then_succeeds() -> None:
    async def scenario() -> None:
        delegate = SequencedLLM(
            [
                LLMProviderRateLimitError("rate limited"),
                LLMResponse(text="recovered"),
            ]
        )
        llm = RetryLLM(
            delegate=delegate,
            max_attempts=3,
            base_delay_seconds=0,
        )
        response = await llm.generate(LLMRequest(prompt="question"))
        assert response.text == "recovered"
        assert delegate.calls == 2

    asyncio.run(scenario())


def test_rejects_zero_max_attempts() -> None:
    delegate = SequencedLLM([])

    with pytest.raises(
        ValueError,
        match="max_attempts must be at least 1",
    ):
        RetryLLM(
            delegate=delegate,
            max_attempts=0,
        )


def test_uses_exponential_backoff_between_retries() -> None:
    async def scenario() -> None:
        delegate = SequencedLLM(
            [
                LLMProviderUnavailableError("failure 1"),
                LLMProviderUnavailableError("failure 2"),
                LLMResponse(text="recovered"),
            ]
        )

        sleeper = RecordingSleeper()
        randomizer = FixedRandomizer(
            [
                0.2,
                0.7,
            ]
        )
        llm = RetryLLM(
            delegate=delegate,
            max_attempts=3,
            base_delay_seconds=0.5,
            sleeper=sleeper,
            randomizer=randomizer,
        )

        response = await llm.generate(LLMRequest(prompt="question"))

        assert response.text == "recovered"
        assert delegate.calls == 3
        assert randomizer.calls == [
            (0.0, 0.5),
            (0.0, 1.0),
        ]

        assert sleeper.delays == [
            0.2,
            0.7,
        ]

    asyncio.run(scenario())


def test_does_not_sleep_after_final_attempt() -> None:
    async def scenario() -> None:
        delegate = SequencedLLM(
            [
                LLMProviderUnavailableError("failure 1"),
                LLMProviderUnavailableError("failure 2"),
                LLMProviderUnavailableError("failure 3"),
            ]
        )

        sleeper = RecordingSleeper()
        randomizer = FixedRandomizer(
            [
                0.2,
                0.7,
            ]
        )
        llm = RetryLLM(
            delegate=delegate,
            max_attempts=3,
            base_delay_seconds=0.5,
            sleeper=sleeper,
            randomizer=randomizer,
        )

        with pytest.raises(LLMProviderUnavailableError):
            await llm.generate(LLMRequest(prompt="question"))

        assert delegate.calls == 3
        assert randomizer.calls == [
            (0.0, 0.5),
            (0.0, 1.0),
        ]

        assert sleeper.delays == [
            0.2,
            0.7,
        ]


    asyncio.run(scenario())


def test_rejects_negative_base_delay() -> None:
    delegate = SequencedLLM([])

    with pytest.raises(
        ValueError,
        match="base_delay_seconds must be non-negative",
    ):
        RetryLLM(
            delegate=delegate,
            base_delay_seconds=-0.1,
        )


def test_backoff_grows_for_four_attempts() -> None:
    async def scenario() -> None:
        delegate = SequencedLLM(
            [
                LLMProviderUnavailableError("failure 1"),
                LLMProviderUnavailableError("failure 2"),
                LLMProviderUnavailableError("failure 3"),
                LLMResponse(text="recovered"),
            ]
        )
        sleeper = RecordingSleeper()
        randomizer = FixedRandomizer(
            [
                0.4,
                1.3,
                2.7,
            ]
        )
        llm = RetryLLM(
            delegate=delegate,
            max_attempts=4,
            base_delay_seconds=1.0,
            sleeper=sleeper,
            randomizer=randomizer,
        )

        response = await llm.generate(LLMRequest(prompt="question"))

        assert response.text == "recovered"
        assert delegate.calls == 4
        assert randomizer.calls == [
            (0.0, 1.0),
            (0.0, 2.0),
            (0.0, 4.0),
        ]

        assert sleeper.delays == [
            0.4,
            1.3,
            2.7,
        ]

    asyncio.run(scenario())


def test_request_error_does_not_backoff() -> None:
    async def scenario() -> None:
        delegate = SequencedLLM([LLMProviderRequestError("invalid request")])
        sleeper = RecordingSleeper()
        randomizer = FixedRandomizer([])
        llm = RetryLLM(
            delegate=delegate,
            max_attempts=3,
            sleeper=sleeper,
            randomizer=randomizer,
        )

        with pytest.raises(LLMProviderRequestError):
            await llm.generate(LLMRequest(prompt="question"))

        assert delegate.calls == 1
        assert randomizer.calls == []
        assert sleeper.delays == []

    asyncio.run(scenario())


class FixedRandomizer:
    def __init__(
        self,
        values: list[float],
    ) -> None:
        self._values = values
        self.calls: list[tuple[float, float]] = []

    def __call__(
        self,
        lower: float,
        upper: float,
    ) -> float:
        self.calls.append((lower, upper))

        index = len(self.calls) - 1
        return self._values[index]


def test_uses_full_jitter_for_backoff() -> None:
    async def scenario() -> None:
        delegate = SequencedLLM(
            [
                LLMProviderUnavailableError("failure 1"),
                LLMProviderUnavailableError("failure 2"),
                LLMResponse(text="recovered"),
            ]
        )

        sleeper = RecordingSleeper()

        randomizer = FixedRandomizer(
            [
                0.2,
                0.7,
            ]
        )

        llm = RetryLLM(
            delegate=delegate,
            max_attempts=3,
            base_delay_seconds=0.5,
            sleeper=sleeper,
            randomizer=randomizer,
        )

        response = await llm.generate(LLMRequest(prompt="question"))

        assert response.text == "recovered"

        assert randomizer.calls == [
            (0.0, 0.5),
            (0.0, 1.0),
        ]

        assert sleeper.delays == [
            0.2,
            0.7,
        ]

    asyncio.run(scenario())


def test_does_not_randomize_after_final_attempt() -> None:
    async def scenario() -> None:
        delegate = SequencedLLM(
            [
                LLMProviderUnavailableError("failure 1"),
                LLMProviderUnavailableError("failure 2"),
                LLMProviderUnavailableError("failure 3"),
            ]
        )

        sleeper = RecordingSleeper()

        randomizer = FixedRandomizer(
            [
                0.2,
                0.7,
            ]
        )

        llm = RetryLLM(
            delegate=delegate,
            max_attempts=3,
            base_delay_seconds=0.5,
            sleeper=sleeper,
            randomizer=randomizer,
        )

        with pytest.raises(LLMProviderUnavailableError):
            await llm.generate(LLMRequest(prompt="question"))
        assert delegate.calls == 3
        assert randomizer.calls == [
            (0.0, 0.5),
            (0.0, 1.0),
        ]

        assert sleeper.delays == [
            0.2,
            0.7,
        ]

    asyncio.run(scenario())
def test_rate_limit_uses_retry_after() -> None:
    async def scenario() -> None:
        delegate = SequencedLLM(
            [
                LLMProviderRateLimitError(
                    "rate limited",
                    retry_after_seconds=5.0,
                ),
                LLMResponse(
                    text="recovered"
                ),
            ]
        )

        sleeper = RecordingSleeper()

        randomizer = FixedRandomizer([])

        llm = RetryLLM(
            delegate=delegate,
            max_attempts=3,
            base_delay_seconds=0.5,
            sleeper=sleeper,
            randomizer=randomizer,
        )

        response = await llm.generate(
            LLMRequest(
                prompt="question"
            )
        )

        assert response.text == "recovered"
        assert delegate.calls == 2

        assert randomizer.calls == []

        assert sleeper.delays == [
            5.0,
        ]

    asyncio.run(scenario())
def test_rate_limit_no_retry_after() -> None:
    async def scenario() -> None:
        delegate = SequencedLLM(
            [
                LLMProviderRateLimitError(
                    "rate limited",
                ),
                LLMResponse(
                    text="recovered"
                ),
            ]
        )

        sleeper = RecordingSleeper()

        randomizer = FixedRandomizer([0.3])

        llm = RetryLLM(
            delegate=delegate,
            max_attempts=3,
            base_delay_seconds=0.5,
            sleeper=sleeper,
            randomizer=randomizer,
        )

        response = await llm.generate(
            LLMRequest(
                prompt="question"
            )
        )

        assert response.text == "recovered"
        assert delegate.calls == 2

        assert randomizer.calls == [(0.0,0.5)]

        assert sleeper.delays == [
            0.3,
        ]

    asyncio.run(scenario())
