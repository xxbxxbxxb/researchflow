from researchflow.application.evidence import digest
from researchflow.domain.research import Evidence
from researchflow.domain.sources import AnchoredEvidence, EvidenceAnchor, SourceSnapshot
from researchflow.ports.retrieval import RetrievalCandidate, RetrievalResult

INDEX_VERSION = 'chunks-800-100-v1'


def chunk_snapshot(snapshot: SourceSnapshot) -> tuple[RetrievalCandidate, ...]:
    chunks = []
    for page in snapshot.pages:
        start = 0
        while start < len(page.text):
            end = min(start + 800, len(page.text))
            if end < len(page.text):
                boundary = page.text.rfind('\n\n', start + 400, end)
                if boundary != -1:
                    end = boundary + 2
            text = page.text[start:end]
            if text.strip():
                identity = digest(f'{snapshot.project_id}\0{snapshot.snapshot_id}\0{page.number}\0{start}\0{end}\0{INDEX_VERSION}')
                chunks.append(RetrievalCandidate(identity, snapshot.project_id, snapshot.snapshot_id, page.number, start, end, text, snapshot.source_uri))
            if end == len(page.text):
                break
            start = end - 100
    return tuple(chunks)


def distinct_candidates(candidates: tuple[RetrievalCandidate, ...], limit: int = 8) -> tuple[RetrievalCandidate, ...]:
    selected: list[RetrievalCandidate] = []
    for candidate in candidates:
        duplicate = False
        for existing in selected:
            if (existing.project_id, existing.snapshot_id, existing.page) == (candidate.project_id, candidate.snapshot_id, candidate.page):
                overlap = max(0, min(existing.end, candidate.end) - max(existing.start, candidate.start))
                if overlap / min(existing.end - existing.start, candidate.end - candidate.start) >= 0.8:
                    duplicate = True
                    break
        if not duplicate:
            selected.append(candidate)
        if len(selected) >= limit:
            break
    return tuple(selected)


class EvidenceSelector:
    def select(self, candidates: RetrievalResult) -> tuple[AnchoredEvidence, ...]:
        selected = []
        for chunk in distinct_candidates(candidates.candidates):
            quote_hash = digest(chunk.text)
            identity = digest('\0'.join((chunk.project_id, chunk.snapshot_id, str(chunk.page), str(chunk.start), str(chunk.end), quote_hash, INDEX_VERSION)))[:32]
            selected.append(AnchoredEvidence(Evidence(identity, chunk.source_uri, f'page={chunk.page};start={chunk.start};end={chunk.end}', chunk.text), chunk.project_id, EvidenceAnchor(chunk.snapshot_id, chunk.page, chunk.start, chunk.end), quote_hash, INDEX_VERSION))
        return tuple(selected)
