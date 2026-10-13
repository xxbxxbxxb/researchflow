import json
from datetime import UTC, datetime
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from researchflow.domain.tool_calls import ToolCall
from researchflow.domain.usage import ModelUsage
from researchflow.infrastructure.llm.errors import (
    LLMProviderProtocolError,
    LLMProviderRateLimitError,
    LLMProviderRequestError,
    LLMProviderUnavailableError,
)
from researchflow.infrastructure.llm.openai_compatible import OpenAICompatibleConfig
from researchflow.infrastructure.llm.retry_after import parse_retry_after
from researchflow.ports.model import ChatRequest, ChatResponse


class MessageEnvelope(BaseModel):
    model_config = ConfigDict(strict=True)
    content: str | None = None
    refusal: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class OpenAIChatModel:
    """One HTTP attempt. Retry and ownership live in ModelRuntime."""
    def __init__(self, client: httpx.AsyncClient, config: OpenAICompatibleConfig) -> None:
        self.client = client
        self.config = config

    def request_body(self, request: ChatRequest) -> dict[str, Any]:
        messages = []
        for msg in request.messages:
            row: dict[str, Any] = {'role':msg.role, 'content':msg.content}
            if msg.tool_call_id:
                row['tool_call_id'] = msg.tool_call_id
            if msg.tool_calls:
                row['tool_calls'] = [{'id':c.call_id,'type':'function','function':{'name':c.name,'arguments':json.dumps(c.arguments)}} for c in msg.tool_calls]
            messages.append(row)
        body: dict[str, Any] = {'model':self.config.model, 'messages':messages, 'max_tokens':request.max_output_tokens}
        if request.tools:
            body['tools'] = list(request.tools)
        return body

    def check_status(self, response: httpx.Response) -> None:
        if response.status_code == 429:
            raise LLMProviderRateLimitError('provider rate limited', retry_after_seconds=parse_retry_after(response.headers.get('retry-after'), datetime.now(UTC)))
        if response.status_code >= 500:
            raise LLMProviderUnavailableError(f'provider unavailable ({response.status_code})')
        if response.status_code >= 400:
            raise LLMProviderRequestError(f'provider rejected request ({response.status_code})')
        if response.is_redirect:
            raise LLMProviderRequestError('provider redirected unexpectedly')

    async def complete(self, request: ChatRequest) -> ChatResponse:
        try:
            response = await self.client.post(self.config.base_url.rstrip('/')+'/chat/completions', headers={'Authorization':'Bearer '+self.config.api_key}, json=self.request_body(request))
        except httpx.TransportError as exc:
            raise LLMProviderUnavailableError('provider transport failed') from exc
        self.check_status(response)
        try:
            data = response.json()
            choice = data['choices'][0]
            if choice.get('finish_reason') in ('length','content_filter'):
                raise ValueError('provider output incomplete')
            msg = MessageEnvelope.model_validate(choice['message'])
            if msg.refusal:
                raise ValueError('provider refused')
            calls = []
            for row in msg.tool_calls:
                fn = row['function']
                args = json.loads(fn['arguments'])
                if not isinstance(args, dict) or not isinstance(fn['name'], str):
                    raise ValueError('tool parameters invalid')
                calls.append(ToolCall(row['id'], fn['name'], args))
            if not calls and not (msg.content and msg.content.strip()):
                raise ValueError('provider output empty')
            usage = None
            if isinstance(data.get('usage'), dict):
                raw = data['usage']
                tokens = (raw.get('prompt_tokens'), raw.get('completion_tokens'))
                if any(x is not None and (type(x) is not int or x < 0) for x in tokens):
                    raise ValueError('usage invalid')
                usage = ModelUsage(*tokens)
            return ChatResponse(msg.content or '', tuple(calls), data.get('model', self.config.model), response.headers.get('x-request-id') or data.get('id'), usage)
        except (KeyError, IndexError, TypeError, ValueError, ValidationError) as exc:
            raise LLMProviderProtocolError('provider response violates chat contract') from exc
