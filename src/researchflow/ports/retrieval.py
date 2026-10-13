from dataclasses import dataclass
from typing import Literal, Protocol

from researchflow.domain.sources import SourceSnapshot


@dataclass(frozen=True)
class EmbeddingBatch:
    vectors: tuple[tuple[float, ...], ...]
    model: str
    dimensions: int


class EmbeddingPort(Protocol):
    model: str
    dimensions: int
    async def embed(self, texts: tuple[str, ...]) -> EmbeddingBatch: ...


@dataclass(frozen=True)
class RetrievalCandidate:
    chunk_id: str
    project_id: str
    snapshot_id: str
    page: int
    start: int
    end: int
    text: str
    source_uri: str
    score: float = 0.0


@dataclass(frozen=True)
class RetrievalResult:
    candidates: tuple[RetrievalCandidate, ...]
    mode: Literal['lexical', 'hybrid']
    embedding_version: str | None


class Retriever(Protocol):
    async def index_snapshot(self, snapshot: SourceSnapshot) -> None: ...
    async def search(self, project_id: str, query: str, source_ids: tuple[str, ...], top_k: int = 8) -> RetrievalResult: ...
