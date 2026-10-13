from researchflow.application.evidence import EvidenceLedger
from researchflow.domain.sources import AnchoredEvidence, SourceSnapshot


class MemoryEvidenceRepository:
    def __init__(self, snapshots: tuple[SourceSnapshot, ...] = ()) -> None:
        self.ledger = EvidenceLedger(snapshots)

    async def add_evidence_batch(self, project_id: str, items: tuple[AnchoredEvidence, ...]) -> tuple[AnchoredEvidence, ...]:
        return self.ledger.add_batch(project_id, items)

    async def get_evidence(self, project_id: str, evidence_id: str) -> AnchoredEvidence | None:
        return self.ledger.get(project_id, evidence_id)
