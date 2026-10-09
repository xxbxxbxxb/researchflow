import asyncio
import math

from researchflow.ports.llm import (
    LLMPort,
    LLMRequest,
    LLMResponse,
)


class DeadlineLLM:
    def __init__(
        self,
        delegate: LLMPort,
        timeout_seconds: float,
    ) -> None:
        if (
            not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
        ):
            raise ValueError(
                "timeout_seconds must be a positive finite number"
            )

        self._delegate = delegate
        self._timeout_seconds = timeout_seconds

    async def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        async with asyncio.timeout(
            self._timeout_seconds
        ):
            return await self._delegate.generate(
                request
            )