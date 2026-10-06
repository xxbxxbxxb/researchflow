from collections.abc import Callable,Awaitable
import asyncio
import random
from researchflow.infrastructure.llm.errors import (
    LLMProviderRateLimitError,
    LLMProviderUnavailableError,
)
from researchflow.ports.llm import (
    LLMPort,
    LLMRequest,
    LLMResponse,
)

RETRYABLE_ERRORS = (
    LLMProviderRateLimitError,
    LLMProviderUnavailableError,
)
Sleeper = Callable[
    [float],
    Awaitable[None],
]
Randomizer = Callable[
    [float, float],
    float,
]
class RetryLLM:
    def __init__(
        self,
        delegate: LLMPort,
        max_attempts: int = 3,
        base_delay_seconds: float = 0.5,
        sleeper: Sleeper = asyncio.sleep,
        randomizer: Randomizer = random.uniform,
    ) -> None:
        if max_attempts < 1:
            raise ValueError(
                "max_attempts must be at least 1"
            )
        if base_delay_seconds < 0:
            raise ValueError(
                "base_delay_seconds must be non-negative"
            )
        self._delegate = delegate
        self._max_attempts = max_attempts
        self._base_delay_seconds = base_delay_seconds
        self._sleeper = sleeper
        self._randomizer = randomizer
    async def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        for attempt in range(
            1,
            self._max_attempts+1,
        ):
            try:
                return await self._delegate.generate(
                    request
                )
            except RETRYABLE_ERRORS:
                if attempt == self._max_attempts:
                    raise
                backoff_cap = (
                    self._base_delay_seconds
                    * (2 ** (attempt - 1))
                )
                delay = self._randomizer(
                    0.0,
                    backoff_cap,
                )

                await self._sleeper(delay)
        raise RuntimeError(
            "unreachable retry state"
        )