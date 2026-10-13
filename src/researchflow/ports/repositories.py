from dataclasses import dataclass
from typing import Protocol

from researchflow.domain.claims import Claim, Verification
from researchflow.domain.knowledge import FollowUpDraft, KnowledgeEntry
from researchflow.domain.projects import TaskRecord
from researchflow.domain.reports import ResearchResult
from researchflow.domain.sources import AnchoredEvidence
from researchflow.ports.sources import SnapshotRepository


class EvidenceRepository(Protocol):
    async def add_evidence_batch(self, project_id: str, items: tuple[AnchoredEvidence, ...]) -> tuple[AnchoredEvidence, ...]: ...
    async def get_evidence(self, project_id: str, evidence_id: str) -> AnchoredEvidence | None: ...


class ResearchReadRepository(SnapshotRepository, Protocol):
    async def get_task(self, project_id: str, task_id: str) -> TaskRecord | None: ...




@dataclass(frozen=True)
class VerificationContext:
    verification: Verification
    claim: Claim
    result: ResearchResult
    is_current: bool


class KnowledgePort(Protocol):
    async def verification_context(self, project_id: str, verification_id: str) -> VerificationContext: ...
    async def get_entry(self, project_id: str, knowledge_id: str) -> KnowledgeEntry | None: ...
    async def accept_entry(self, entry: KnowledgeEntry) -> KnowledgeEntry: ...
    async def replace_entry(self, old_id: str, entry: KnowledgeEntry) -> KnowledgeEntry: ...
    async def save_override(self, project_id: str, old_id: str, verification: Verification, result: ResearchResult) -> Verification: ...
    async def save_draft(self, draft: FollowUpDraft) -> FollowUpDraft: ...
