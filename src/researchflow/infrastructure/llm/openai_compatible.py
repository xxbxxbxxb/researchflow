from dataclasses import dataclass

import httpx

from researchflow.infrastructure.llm.errors import(
    LLMProviderError,
    LLMProviderProtocolError,
    LLMProviderRateLimitError,
    LLMProviderRequestError,
    LLMProviderUnavailableError,
)
from researchflow.ports.llm import LLMRequest,LLMResponse

@dataclass(frozen=True)
class OpenAICompatibleConfig:
    base_url: str
    api_key: str
    model: str


class OpenAICompatibleLLM:
    def __init__(self, client: httpx.AsyncClient, config: OpenAICompatibleConfig) -> None:
        self._client = client
        self._config = config
        
    async def generate(
        self,
        request: LLMRequest,
    ) ->LLMResponse:
        try:
            response = await self._client.post(
                (
                    f"{self._config.base_url.rstrip('/')}"
                    "/chat/completions"
                ),
                headers={
                    "Authorization":(
                        f"Bearer {self._config.api_key}"
                    )
                },
                json={
                    "model": self._config.model,
                    "messages": [
                        {
                            "role":"user",
                            "content":request.prompt,
                        }
                    ],
                },
            )
            
        except httpx.TimeoutException as exc:
            raise LLMProviderUnavailableError(
                "LLM provider request time out"
            ) from exc
        except httpx.TransportError as exc:
            raise LLMProviderUnavailableError(
                "LLM provider request transport failed"
            ) from exc
        if response.status_code in {
            400,
            401,
            403,
            404,
            422,
        }:
            raise LLMProviderRequestError(
                f"LLM provider rejected request:"
                f"{response.status_code}"
            )
        if response.status_code == 429:

            retry_after_seconds: float | None = None
            retry_after = response.headers.get(
                "Retry-After"
            )
        
            if retry_after is not None:
                try:
                    parsed_retry_after = float(
                        retry_after
                    )
                except ValueError:
                    pass
                else:
                    if parsed_retry_after >= 0:
                        retry_after_seconds = (
                            parsed_retry_after
                        )
        
            raise LLMProviderRateLimitError(
                "LLM provider rate limited the request",
                retry_after_seconds=retry_after_seconds,
            )
        if 500 <= response.status_code <= 599:
            raise LLMProviderUnavailableError(
                f"LLM provider unavailable:"
                f"{response.status_code}"
            )
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMProviderRequestError(
                f"LLM provider returned unexpected status:"
                f"{response.status_code}"
            ) from exc
        
        try:
            text = (
                response.json()["choices"][0]["message"]["content"]
            )
        except(
            KeyError,
            IndexError,
            TypeError,
            ValueError,
        ) as exc:
            raise LLMProviderProtocolError(
                "LLM provider returned an invalid response"
            ) from exc
        if not isinstance(text, str) or not text.strip():
            raise LLMProviderProtocolError(
                "LLM provider returned empty content"
            )
        return LLMResponse(text=text)