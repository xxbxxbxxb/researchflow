from typing import Protocol

from researchflow.domain.sources import AnchoredEvidence
from researchflow.domain.projects import TaskRecord
from researchflow.ports.sources import SnapshotRepository


class EvidenceRepository(Protocol):
    async def add_evidence_batch(self, project_id: str, items: tuple[AnchoredEvidence, ...]) -> tuple[AnchoredEvidence, ...]: ...
    async def get_evidence(self, project_id: str, evidence_id: str) -> AnchoredEvidence | None: ...


class ResearchReadRepository(SnapshotRepository, Protocol):
    async def get_task(self, project_id: str, task_id: str) -> TaskRecord | None: ...
