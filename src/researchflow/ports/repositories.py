from typing import Protocol

from researchflow.domain.sources import AnchoredEvidence


class EvidenceRepository(Protocol):
    async def add_evidence_batch(self, project_id: str, items: tuple[AnchoredEvidence, ...]) -> tuple[AnchoredEvidence, ...]: ...
    async def get_evidence(self, project_id: str, evidence_id: str) -> AnchoredEvidence | None: ...
