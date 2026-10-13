from datetime import datetime, timezone
from hashlib import sha256
from pathlib import PurePath

from researchflow.domain.sources import SourceSnapshot
from researchflow.ports.sources import (
    BlobPort,
    FetcherPort,
    ParserPort,
    PreparedSource,
    SnapshotRepository,
    SourceInput,
)


class IngestSource:
    def __init__(self, repository: SnapshotRepository, blobs: BlobPort, parser: ParserPort, fetcher: FetcherPort | None = None) -> None:
        self.repository, self.blobs, self.parser, self.fetcher = repository, blobs, parser, fetcher

    async def prepare(self, project_id: str, source: SourceInput) -> PreparedSource:
        if not project_id.strip():
            raise ValueError('project_id is required')
        fetched_at = datetime.now(timezone.utc)
        if source.url is not None:
            if self.fetcher is None:
                raise ValueError('URL ingestion requires a safe source fetcher')
            fetched = await self.fetcher.fetch(source.url)
            data, media, uri, fetched_at = fetched.data, fetched.media_type, fetched.final_url, fetched.fetched_at
        else:
            assert source.data is not None
            data, media = source.data, source.media_type
            # An upload name is metadata, never a disk path.
            uri = 'upload:' + PurePath(source.filename.replace('\\', '/')).name
        parsed = await self.parser.parse_async(data, media)
        key = self.blobs.put(data)
        identity = sha256(f'{project_id}\0{uri}\0{key}\0{parsed.parser_version}'.encode()).hexdigest()
        snapshot = SourceSnapshot(identity, project_id, uri, key, parsed.pages, parsed.parser_version, fetched_at)
        return PreparedSource(snapshot, key, parsed.title or uri)

    async def execute(self, project_id: str, source: SourceInput) -> SourceSnapshot:
        prepared = await self.prepare(project_id, source)
        return await self.repository.save_snapshot(prepared.snapshot, prepared.title)
