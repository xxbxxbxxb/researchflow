from dataclasses import dataclass

import httpx

from researchflow.ports.llm import LLMRequest,LLMResponse

@dataclass(frozen=True)
class OpenAICompatibleConfig:
    base_url: str
    api_key: str
    model: str

class LLMProviderError(RuntimeError):
    pass

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
            
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise LLMProviderError(
                "LLM provider request failed"
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
            raise LLMProviderError(
                "LLM provider returned an invalid response"
            ) from exc
        if not isinstance(text, str) or not text.strip():
            raise LLMProviderError(
                "LLM provider returned empty content"
            )
        return LLMResponse(text=text)