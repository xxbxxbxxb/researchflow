import pytest

from researchflow.application.use_cases.prepare_research_task import (
    EvidenceInput,
    PrepareResearchTask,
)
from researchflow.domain.research import (
    Evidence,
    ResearchTask,
)


def sample_input() -> EvidenceInput:
    return EvidenceInput(
        source="paper:EEGAlign",
        locator="Methods, Section 3",
        text=(
            "The model aligns EEG with "
            "text and audio features."
        ),
    )


def test_prepares_task_with_traceable_evidence() -> None:
    task = PrepareResearchTask().execute(
        task_id="task-001",
        question="  Why use two alignment objectives?  ",
        items=[
            sample_input(),
            EvidenceInput(
                source="paper:EEGAlign",
                locator="Experiments, Table 2",
                text=(
                    "Ablation results are reported "
                    "for the alignment objectives."
                ),
            ),
        ],
    )

    assert task.question == (
        "Why use two alignment objectives?"
    )

    assert [
        evidence.evidence_id
        for evidence in task.evidences
    ] == [
        "task-001:E001",
        "task-001:E002",
    ]

    assert task.evidences[0].source == (
        "paper:EEGAlign"
    )

    assert task.evidences[0].locator == (
        "Methods, Section 3"
    )

    assert task.evidences[0].text == (
        sample_input().text
    )


def test_rejects_empty_evidence_input() -> None:
    with pytest.raises(
        ValueError,
        match="at least one evidence",
    ):
        PrepareResearchTask().execute(
            task_id="task-001",
            question="Why?",
            items=[],
        )


def test_rejects_blank_question() -> None:
    with pytest.raises(
        ValueError,
        match="question must not be blank",
    ):
        PrepareResearchTask().execute(
            task_id="task-001",
            question="  ",
            items=[sample_input()],
        )


def test_rejects_blank_evidence_text() -> None:
    with pytest.raises(
        ValueError,
        match="text must not be blank",
    ):
        PrepareResearchTask().execute(
            task_id="task-001",
            question="Why?",
            items=[
                EvidenceInput(
                    "paper:EEGAlign",
                    "Methods",
                    "   ",
                )
            ],
        )


def test_input_list_changes_do_not_change_task() -> None:
    items = [sample_input()]

    task = PrepareResearchTask().execute(
        task_id="task-001",
        question="Why?",
        items=items,
    )

    items.append(sample_input())

    assert len(task.evidences) == 1
    assert isinstance(task.evidences, tuple)
    
def test_rejects_exceed_evidences_input() -> None:
    items = [sample_input() for _ in range(21)]
    with pytest.raises(
        ValueError,
        match="at most 20 evidence items",
    ):
        PrepareResearchTask().execute(
            task_id="task-001",
            question="Why?",
            items=items,
        )
def test_rejects_duplicate_evidence_ids() -> None:
    evidence_1 = Evidence(
        evidence_id="E001",
        source="paper-A",
        locator="Section 3",
        text="First evidence",
    )
    evidence_2 = Evidence(
            evidence_id="E001",
            source="paper-B",
            locator="Section 4",
            text="Second evidence",
        )
    with pytest.raises(
        ValueError,
        match="evidence_id must be unique within a task",
    ):
        
        ResearchTask(
            task_id="task-001",
            question="Why use dual-axis alignment?",
            evidences=(
                evidence_1,
                evidence_2,
            ),
        )