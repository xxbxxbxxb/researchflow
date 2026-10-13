from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from researchflow.domain.sources import SnapshotPage, SourceSnapshot


class SourceAccessDeniedError(ValueError):
    pass


@dataclass(frozen=True)
class SourceInput:
    filename: str = ''
    data: bytes | None = None
    media_type: str = 'text/plain'
    url: str | None = None

    def __post_init__(self) -> None:
        if (self.data is None) == (self.url is None):
            raise ValueError('source requires exactly one of data or URL')


@dataclass(frozen=True)
class FetchedSource:
    original_url: str
    final_url: str
    data: bytes
    media_type: str
    fetched_at: datetime


@dataclass(frozen=True)
class ParsedDocument:
    pages: tuple[SnapshotPage, ...]
    parser_version: str
    title: str = ''


@dataclass(frozen=True)
class SourceCandidate:
    source_id: str
    title: str
    url: str
    summary: str
    authors: tuple[str, ...]
    published_at: datetime


@dataclass(frozen=True)
class PreparedSource:
    snapshot: SourceSnapshot
    blob_key: str
    title: str


class ParserPort(Protocol):
    def parse(self, data: bytes, mime_type: str) -> ParsedDocument: ...
    async def parse_async(self, data: bytes, mime_type: str) -> ParsedDocument: ...


class FetcherPort(Protocol):
    async def fetch(self, url: str) -> FetchedSource: ...


class SourceSearch(Protocol):
    async def search(self, query: str, limit: int = 8) -> tuple[SourceCandidate, ...]: ...


class BlobPort(Protocol):
    def put(self, data: bytes) -> str: ...
    def get(self, content_hash: str) -> bytes: ...


class SnapshotRepository(Protocol):
    async def save_snapshot(self, snapshot: SourceSnapshot, title: str | None = None) -> SourceSnapshot: ...
    async def get_snapshot(self, project_id: str, snapshot_id: str) -> SourceSnapshot | None: ...
    async def list_snapshots(self, project_id: str) -> tuple[SourceSnapshot, ...]: ...
