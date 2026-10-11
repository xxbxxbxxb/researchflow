from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class Evidence:
    evidence_id: str
    source: str
    locator: str
    text: str
    
    def __post_init__(self) -> None:
        for field in (
            "evidence_id",
            "source",
            "locator",
            "text",
        ):
            if not getattr(self,field).strip():
                raise ValueError(
                    f"{field} must not be blank"
                )
@dataclass(frozen=True, slots=True)
class ResearchTask:
    task_id: str
    question: str
    evidences: tuple[Evidence, ...]

    def __post_init__(self) -> None:
        if not self.task_id.strip():
            raise ValueError(
                "task_id must not be blank"
            )

        if not self.question.strip():
            raise ValueError(
                "question must not be blank"
            )

        if len(self.question.strip()) > 5000:
            raise ValueError(
                "question must not exceed 5000 characters"
            )

        ids = [
            evidence.evidence_id
            for evidence in self.evidences
        ]

        if len(ids) != len(set(ids)):
            raise ValueError(
                "evidence_id must be unique within a task"
            )