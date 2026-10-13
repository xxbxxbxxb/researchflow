from dataclasses import dataclass
from datetime import UTC, datetime
import unicodedata

from researchflow.domain.research import Evidence


def normalize_text(text: str) -> str:
    return unicodedata.normalize('NFC', text.replace('\r\n', '\n').replace('\r', '\n'))


@dataclass(frozen=True, slots=True)
class SnapshotPage:
    number: int
    text: str

    def __post_init__(self) -> None:
        if self.number < 1:
            raise ValueError('physical page must be positive')
        object.__setattr__(self, 'text', normalize_text(self.text))


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    snapshot_id: str
    project_id: str
    source_uri: str
    content_hash: str
    pages: tuple[SnapshotPage, ...]
    parser_version: str
    fetched_at: datetime

    def __post_init__(self) -> None:
        for name in ('snapshot_id', 'project_id', 'source_uri', 'content_hash', 'parser_version'):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f'{name} must not be blank')
        object.__setattr__(self, 'pages', tuple(self.pages))
        if len({p.number for p in self.pages}) != len(self.pages):
            raise ValueError('duplicate physical page')
        if self.fetched_at.tzinfo is None:
            raise ValueError('snapshot time must be timezone aware')
        object.__setattr__(self, 'fetched_at', self.fetched_at.astimezone(UTC))


@dataclass(frozen=True, slots=True)
class EvidenceAnchor:
    snapshot_id: str
    page: int
    start: int
    end: int
    normalization_version: str = 'nfc-lf-v1'

    def __post_init__(self) -> None:
        if self.page < 1 or self.start < 0 or self.end <= self.start:
            raise ValueError('invalid evidence coordinates')


@dataclass(frozen=True, slots=True)
class AnchoredEvidence:
    evidence: Evidence
    project_id: str
    anchor: EvidenceAnchor
    quote_hash: str
    extractor_version: str = 'anchor-v1'
