from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256

from researchflow.domain.errors import EvidenceConflict, ProjectBoundaryError
from researchflow.domain.research import Evidence
from researchflow.domain.sources import AnchoredEvidence, EvidenceAnchor, SourceSnapshot, SnapshotPage, normalize_text


def digest(text: str) -> str:
    return sha256(text.encode('utf-8')).hexdigest()


def validate_anchor(item: AnchoredEvidence, snapshot: SourceSnapshot) -> None:
    if item.project_id != snapshot.project_id:
        raise ProjectBoundaryError('evidence belongs to another project')
    if item.anchor.snapshot_id != snapshot.snapshot_id:
        raise ValueError('evidence references another snapshot')
    page = next((p for p in snapshot.pages if p.number == item.anchor.page), None)
    if page is None or item.anchor.end > len(page.text):
        raise ValueError('evidence is outside the saved page')
    quote = page.text[item.anchor.start:item.anchor.end]
    if quote != item.evidence.text or digest(quote) != item.quote_hash:
        raise ValueError('evidence quote or hash does not match the snapshot')
    if item.anchor.normalization_version != 'nfc-lf-v1':
        raise ValueError('unsupported anchor normalization version')


def anchor_evidence(snapshot: SourceSnapshot, page: int, start: int, end: int, extractor_version: str = 'anchor-v1') -> AnchoredEvidence:
    source_page = next((p for p in snapshot.pages if p.number == page), None)
    if source_page is None or start < 0 or end > len(source_page.text) or end <= start:
        raise ValueError('invalid evidence coordinates')
    quote = source_page.text[start:end]
    quote_hash = digest(quote)
    evidence_id = digest('\0'.join((snapshot.project_id, snapshot.snapshot_id, str(page), str(start), str(end), quote_hash, extractor_version)))[:32]
    result = AnchoredEvidence(Evidence(evidence_id, snapshot.source_uri, f'page={page};start={start};end={end}', quote), snapshot.project_id, EvidenceAnchor(snapshot.snapshot_id, page, start, end), quote_hash, extractor_version)
    validate_anchor(result, snapshot)
    return result


def manual_evidence(project_id: str, evidence: Evidence) -> tuple[SourceSnapshot, AnchoredEvidence]:
    text = normalize_text(evidence.text)
    snapshot_id = digest(project_id + '\0' + evidence.source + '\0' + evidence.locator + '\0' + text)
    snapshot = SourceSnapshot(snapshot_id, project_id, 'manual:' + evidence.evidence_id, digest(text), (SnapshotPage(1, text),), 'manual-v1', datetime.now(UTC))
    item = anchor_evidence(snapshot, 1, 0, len(text))
    return snapshot, replace(item, evidence=replace(evidence, text=text))


class EvidenceLedger:
    def __init__(self, snapshots: tuple[SourceSnapshot, ...] = ()) -> None:
        self._snapshots = {(s.project_id, s.snapshot_id): s for s in snapshots}
        self._items: dict[tuple[str, str], AnchoredEvidence] = {}

    def get(self, project_id: str, evidence_id: str) -> AnchoredEvidence | None:
        return self._items.get((project_id, evidence_id))

    def add_batch(self, project_id: str, items: tuple[AnchoredEvidence, ...]) -> tuple[AnchoredEvidence, ...]:
        pending: dict[tuple[str, str], AnchoredEvidence] = {}
        for item in items:
            if item.project_id != project_id:
                raise ProjectBoundaryError('evidence belongs to another project')
            snapshot = self._snapshots.get((project_id, item.anchor.snapshot_id))
            if snapshot is None:
                raise ValueError('saved snapshot is missing')
            validate_anchor(item, snapshot)
            key = (project_id, item.evidence.evidence_id)
            previous = pending.get(key, self._items.get(key))
            if previous is not None and previous != item:
                raise EvidenceConflict('evidence identity has conflicting content')
            pending[key] = item
        self._items.update(pending)
        return tuple(self._items[(project_id, item.evidence.evidence_id)] for item in items)
