from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Claim:
    """One research statement and its declared evidence references."""

    claim_id: str
    task_id: str
    text: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.claim_id.strip():
            raise ValueError(
                "claim_id must not be blank"
            )

        if not self.task_id.strip():
            raise ValueError(
                "task_id must not be blank"
            )

        if not self.text.strip():
            raise ValueError(
                "claim text must not be blank"
            )

        if not self.evidence_ids:
            raise ValueError(
                "claim must reference evidence"
            )

        if any(
            not evidence_id.strip()
            for evidence_id in self.evidence_ids
        ):
            raise ValueError(
                "evidence_id must not be blank"
            )

        if len(set(self.evidence_ids)) != len(
            self.evidence_ids
        ):
            raise ValueError(
                "claim evidence_ids must be unique"
            )