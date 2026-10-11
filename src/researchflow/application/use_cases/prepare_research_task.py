from dataclasses import dataclass
from typing import Sequence

from researchflow.domain.research import (
    Evidence,
    ResearchTask,
)


@dataclass(frozen=True, slots=True)
class EvidenceInput:
    source: str
    locator: str
    text: str


class PrepareResearchTask:
    def execute(
        self,
        *,
        task_id: str,
        question: str,
        items: Sequence[EvidenceInput],
    ) -> ResearchTask:

        clean_id = task_id.strip()

        if not clean_id:
            raise ValueError(
                "task_id must not be blank"
            )

        if not items:
            raise ValueError(
                "at least one evidence item is required"
            )

        if len(items) > 20:
            raise ValueError(
                "at most 20 evidence items are supported"
            )

        evidences = tuple(
            Evidence(
                evidence_id=f"{clean_id}:E{index:03d}",
                source=item.source,
                locator=item.locator,
                text=item.text,
            )
            for index, item in enumerate(
                items,
                start=1,
            )
        )

        return ResearchTask(
            task_id=clean_id,
            question=question.strip(),
            evidences=evidences,
        )