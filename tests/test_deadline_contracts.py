import asyncio

import pytest



from researchflow.infrastructure.llm.deadline_llm import (
    DeadlineLLM,
)
from researchflow.infrastructure.llm.errors import (
    LLMProviderRequestError,
)
from researchflow.ports.llm import (
    LLMRequest,
    LLMResponse,
)


class RequestErrorLLM:
    async def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        raise LLMProviderRequestError(
            "invalid request"
        )


class TimeoutOnceThenSuccessLLM:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(
        self,
        request: LLMRequest,
    ) -> LLMResponse:
        self.calls += 1

        if self.calls == 1:
            await asyncio.Event().wait()

        return LLMResponse(
            text="recovered"
        )


def test_deadline_preserves_request_error() -> None:
    async def scenario() -> None:
        llm = DeadlineLLM(
            delegate=RequestErrorLLM(),
            timeout_seconds=1.0,
        )

        with pytest.raises(
            LLMProviderRequestError
        ):
            await llm.generate(
                LLMRequest(
                    prompt="invalid question"
                )
            )

    asyncio.run(scenario())


def test_new_generate_gets_fresh_budget() -> None:
    async def scenario() -> None:
        delegate = TimeoutOnceThenSuccessLLM()

        llm = DeadlineLLM(
            delegate=delegate,
            timeout_seconds=0.05,
        )

        with pytest.raises(TimeoutError):
            await llm.generate(
                LLMRequest(
                    prompt="first question"
                )
            )

        response = await llm.generate(
            LLMRequest(
                prompt="second question"
            )
        )

        assert response.text == "recovered"
        assert delegate.calls == 2

    asyncio.run(scenario())

def test_cancel_generate_task() -> None:

    class CancellableLLM:
        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.cancelled = False

        async def generate(
            self,
            request: LLMRequest,
        ) -> LLMResponse:
            self.started.set()

            try:
                await asyncio.Event().wait()

            except asyncio.CancelledError:
                self.cancelled = True
                raise

            raise AssertionError("unreachable")

    async def scenario() -> None:
        delegate = CancellableLLM()

        llm = DeadlineLLM(
            delegate=delegate,
            timeout_seconds=10.0,
        )

        task = asyncio.create_task(
            llm.generate(
                LLMRequest(prompt="question")
            )
        )

        # 等待底层 LLM 真正开始执行
        await asyncio.wait_for(
            delegate.started.wait(),
            timeout=1.0,
        )

        # 此时再从外部取消 Task
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert delegate.cancelled is True
        assert task.cancelled() is True

    asyncio.run(scenario())