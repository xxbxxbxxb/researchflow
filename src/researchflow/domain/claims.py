from dataclasses import dataclass
from datetime import datetime
from typing import Literal

VerificationStatus = Literal['supported', 'contradicted', 'insufficient', 'inconclusive']


@dataclass(frozen=True, slots=True)
class Claim:
    claim_id: str
    task_id: str
    project_id: str
    text: str
    proposed_evidence_ids: tuple[str, ...]
    qualifiers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.text.strip() or len(self.text) > 2000:
            raise ValueError('claim must have 1 to 2000 characters')
        if not all(x.strip() for x in (self.claim_id, self.task_id, self.project_id)):
            raise ValueError('claim identity and scope are required')
        object.__setattr__(self, 'proposed_evidence_ids', tuple(dict.fromkeys(self.proposed_evidence_ids)))
        object.__setattr__(self, 'qualifiers', tuple(self.qualifiers))


@dataclass(frozen=True, slots=True)
class Verification:
    verification_id: str
    claim_id: str
    status: VerificationStatus
    accepted_evidence_ids: tuple[str, ...]
    rationale: str
    checks: tuple[str, ...]
    verifier_version: str
    model_metadata: tuple[tuple[str, str], ...]
    verified_at: datetime
    supersedes_id: str | None = None
    actor: str | None = None

    def __post_init__(self) -> None:
        if self.status not in ('supported', 'contradicted', 'insufficient', 'inconclusive'):
            raise ValueError('unknown verification status')
        if not self.rationale.strip():
            raise ValueError('verification must explain its judgment')
        if self.status == 'supported' and not self.accepted_evidence_ids:
            raise ValueError('supported requires accepted evidence')
