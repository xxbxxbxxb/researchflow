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

class RetryLLM:
    def __init__(
        self,
        delegate: LLMPort,
        max_attempts: int = 3,
    ) -> None:
        if max_attempts < 1:
            raise ValueError(
                "max_attempts must be at least 1"
            )
        self._delegate = delegate
        self._max_attempts = max_attempts
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
        raise RuntimeError(
            "unreachable retry state"
        )