import math
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx

from researchflow.infrastructure.llm.errors import LLMProviderUnavailableError, LLMProviderRequestError, LLMProviderRateLimitError
from researchflow.infrastructure.llm.retry_after import parse_retry_after
from researchflow.ports.retrieval import EmbeddingBatch


@dataclass
class OpenAIEmbeddings:
    client: httpx.AsyncClient = field(repr=False)
    base_url: str
    api_key: str = field(repr=False)
    model: str
    dimensions: int

    async def embed(self, texts: tuple[str, ...]) -> EmbeddingBatch:
        if not 1 <= self.dimensions <= 4096 or not self.model.strip() or len(texts) > 128 or any(not text.strip() or len(text) > 5000 for text in texts):
            raise ValueError('invalid embedding configuration/input')
        if not texts:
            return EmbeddingBatch((), self.model, self.dimensions)
        try:
            response = await self.client.post(self.base_url.rstrip('/') + '/embeddings', headers={'Authorization': 'Bearer ' + self.api_key}, json={'model': self.model, 'input': list(texts), 'encoding_format': 'float', 'dimensions': self.dimensions})
        except httpx.TransportError as exc:
            raise LLMProviderUnavailableError('embedding transport failed') from exc
        if response.status_code == 429:
            raise LLMProviderRateLimitError('embedding rate limited', retry_after_seconds=parse_retry_after(response.headers.get('retry-after'), datetime.now(timezone.utc)))
        if response.status_code >= 500:
            raise LLMProviderUnavailableError('embedding provider unavailable')
        if response.status_code >= 300:
            raise LLMProviderRequestError('embedding provider rejected request')
        try:
            payload = response.json()
            if payload.get('model') != self.model or len(payload['data']) != len(texts):
                raise ValueError('model or vector count mismatch')
            vectors = {}
            for row in payload['data']:
                index, vector = row['index'], row['embedding']
                if type(index) is not int or not 0 <= index < len(texts) or index in vectors or not isinstance(vector, list) or len(vector) != self.dimensions:
                    raise ValueError('vector shape mismatch')
                if any(type(v) not in {int, float} or not math.isfinite(v) for v in vector) or not any(v != 0 for v in vector):
                    raise ValueError('vector values invalid')
                vectors[index] = tuple(float(v) for v in vector)
            return EmbeddingBatch(tuple(vectors[i] for i in range(len(texts))), self.model, self.dimensions)
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError('embedding_protocol: invalid embedding response') from exc
