from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, literal_column, or_, select
from sqlalchemy.dialects.postgresql import insert

from researchflow.application.retrieval import INDEX_VERSION, chunk_snapshot, distinct_candidates
from researchflow.domain.sources import SourceSnapshot
from researchflow.infrastructure.storage.database import Database
from researchflow.infrastructure.storage.models import ChunkRow, SnapshotRow
from researchflow.ports.retrieval import EmbeddingPort, RetrievalCandidate, RetrievalResult


class PostgresRetriever:
    def __init__(self, database: Database, embeddings: EmbeddingPort | None = None) -> None:
        self.database, self.embeddings = database, embeddings

    @property
    def namespace(self) -> str | None:
        return f'{self.embeddings.model}:{self.embeddings.dimensions}:{INDEX_VERSION}' if self.embeddings else None

    async def index_snapshot(self, snapshot: SourceSnapshot) -> None:
        chunks = chunk_snapshot(snapshot)
        vectors: list[tuple[float,...] | None] = [None] * len(chunks)
        if self.embeddings:
            for offset in range(0, len(chunks), 32):
                batch = await self.embeddings.embed(tuple(c.text for c in chunks[offset:offset+32]))
                if batch.model != self.embeddings.model or batch.dimensions != self.embeddings.dimensions or len(batch.vectors) != len(chunks[offset:offset+32]):
                    raise ValueError('index_version_mismatch: embedding namespace changed')
                vectors[offset:offset+32] = list(batch.vectors)
        async with self.database.session.begin() as session:
            for chunk, vector in zip(chunks, vectors, strict=True):
                values = {key:getattr(chunk,key) for key in ('project_id','chunk_id','snapshot_id','page','start','end','text')}
                values.update(embedding=list(vector) if vector is not None else None, embedding_version=self.namespace)
                stmt = insert(ChunkRow).values(**values).on_conflict_do_update(index_elements=['project_id','chunk_id'], set_={'embedding':values['embedding'], 'embedding_version':self.namespace})
                await session.execute(stmt)

    async def search(self, project_id: str, query: str, source_ids: tuple[str, ...], top_k: int = 8) -> RetrievalResult:
        if not project_id.strip() or not query.strip() or len(query) > 5000 or not 1 <= top_k <= 8:
            raise ValueError('invalid retrieval query or limit')
        filters = [ChunkRow.project_id == project_id]
        if source_ids:
            filters.append(ChunkRow.snapshot_id.in_(source_ids))
        async with self.database.session() as session:
            namespaces = (await session.scalars(select(ChunkRow.embedding_version).where(*filters, ChunkRow.embedding.is_not(None)).distinct())).all()
            if self.embeddings and any(namespace != self.namespace for namespace in namespaces):
                raise ValueError('index_version_mismatch: reindex sources explicitly before changing embedding model/dimension')
            vector_active = bool(self.embeddings and namespaces)
            config: Any = literal_column("'simple'::regconfig")
            document = func.to_tsvector(config, ChunkRow.text)
            terms = func.plainto_tsquery(config, query)
            rank = func.ts_rank_cd(document, terms)
            trigram = func.word_similarity(query, ChunkRow.text)
            lexical_score = rank + trigram
            lexical = (await session.scalars(select(ChunkRow).where(*filters, or_(document.op('@@')(terms), trigram > 0.08)).order_by(lexical_score.desc(), ChunkRow.chunk_id).limit(32))).all()
            vector_rows: Sequence[ChunkRow] = []
            if vector_active:
                assert self.embeddings is not None
                batch = await self.embeddings.embed((query,))
                if batch.model != self.embeddings.model or batch.dimensions != self.embeddings.dimensions:
                    raise ValueError('index_version_mismatch: query embedding changed')
                distance = ChunkRow.embedding.cosine_distance(list(batch.vectors[0]))
                vector_rows = (await session.scalars(select(ChunkRow).where(*filters, ChunkRow.embedding_version == self.namespace, func.vector_dims(ChunkRow.embedding) == batch.dimensions).order_by(distance, ChunkRow.chunk_id).limit(32))).all()
            ranks: dict[str, float] = {}
            rows = {}
            for group in (lexical, vector_rows):
                for rank_number, row in enumerate(group, 1):
                    ranks[row.chunk_id] = ranks.get(row.chunk_id, 0.0) + 1.0 / (60 + rank_number)
                    rows[row.chunk_id] = row
            ordered = sorted(rows.values(), key=lambda row:(-ranks[row.chunk_id], row.chunk_id))
            uris = {sid:uri for sid,uri in (await session.execute(select(SnapshotRow.snapshot_id, SnapshotRow.source_uri).where(SnapshotRow.project_id == project_id))).all()}
            candidates = tuple(RetrievalCandidate(row.chunk_id, row.project_id, row.snapshot_id, row.page, row.start, row.end, row.text, uris[row.snapshot_id], ranks[row.chunk_id]) for row in ordered)
            return RetrievalResult(distinct_candidates(candidates, top_k), 'hybrid' if vector_active else 'lexical', self.namespace if vector_active else None)
