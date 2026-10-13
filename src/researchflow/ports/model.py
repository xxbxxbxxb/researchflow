from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from researchflow.domain.tool_calls import ToolCall
from researchflow.domain.usage import ModelUsage


class ModelCallError(RuntimeError):
    """Model boundary failure; cancellation is deliberately not a subtype."""


@dataclass(frozen=True, slots=True)
class ChatMessage:
    role: Literal['system', 'user', 'assistant', 'tool']
    content: str
    tool_call_id: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True, slots=True)
class ChatRequest:
    messages: tuple[ChatMessage, ...]
    tools: tuple[dict[str, Any], ...] = ()
    response_schema: dict[str, Any] | None = None
    operation: str = 'chat'
    max_output_tokens: int = 4096


@dataclass(frozen=True, slots=True)
class ChatResponse:
    text: str = ''
    tool_calls: tuple[ToolCall, ...] = ()
    model: str = ''
    request_id: str | None = None
    usage: ModelUsage | None = None


class ChatModelPort(Protocol):
    async def complete(self, request: ChatRequest) -> ChatResponse: ...
