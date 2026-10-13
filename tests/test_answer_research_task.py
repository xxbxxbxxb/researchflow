import asyncio

import pytest

from researchflow.application.use_cases.answer_research_task import (
    AnswerResearchTask,
    InvalidGroundedAnswerError,
)
from researchflow.application.use_cases.prepare_research_task import (
    EvidenceInput,
    PrepareResearchTask,
)
from researchflow.domain.research import ResearchTask
from researchflow.infrastructure.llm.fake_llm import FakeLLM


def sample_task() -> ResearchTask:
    return PrepareResearchTask().execute(
        task_id="task-001",
        question="双轴对齐有什么作用？",
        items=[
            EvidenceInput(
                source="paper:EEGAlign",
                locator="Methods, Section 3",
                text="模型分别对齐 EEG 与文本、音频特征。",
            ),
            EvidenceInput(
                source="paper:EEGAlign",
                locator="Experiments, Table 2",
                text="论文报告了不同对齐目标的消融实验。",
            ),
        ],
    )


def test_answer_maps_citation_aliases_to_evidence_ids() -> None:
    llm = FakeLLM(
        "采用两种对齐目标 [E1]；有消融实验 [E2][E1]。"
    )

    result = asyncio.run(
        AnswerResearchTask(llm).execute(sample_task())
    )

    assert result.status == "answered"
    assert result.task_id == "task-001"

    assert result.cited_evidence_ids == (
        "task-001:E001",
        "task-001:E002",
    )

    assert "[E1]" in result.text


def test_prompt_contains_question_and_traceable_sources() -> None:
    llm = FakeLLM(
        "根据材料，存在两类对齐目标 [E1]。"
    )

    asyncio.run(
        AnswerResearchTask(llm).execute(sample_task())
    )

    assert llm.last_request is not None

    prompt = llm.last_request.prompt

    assert "双轴对齐有什么作用？" in prompt
    assert '"alias": "E1"' in prompt
    assert '"evidence_id": "task-001:E001"' in prompt
    assert "Methods, Section 3" in prompt

    assert (
        "模型分别对齐 EEG 与文本、音频特征。"
        in prompt
    )


def test_rejects_unknown_citation() -> None:
    llm = FakeLLM("结论 [E99]。")

    with pytest.raises(
        InvalidGroundedAnswerError,
        match="unknown evidence citation",
    ):
        asyncio.run(
            AnswerResearchTask(llm).execute(sample_task())
        )


def test_rejects_answer_without_citation() -> None:
    llm = FakeLLM("没有任何引用的回答。")

    with pytest.raises(
        InvalidGroundedAnswerError,
        match="at least one",
    ):
        asyncio.run(
            AnswerResearchTask(llm).execute(sample_task())
        )


def test_allows_explicit_insufficient_evidence() -> None:
    llm = FakeLLM("INSUFFICIENT_EVIDENCE")

    result = asyncio.run(
        AnswerResearchTask(llm).execute(sample_task())
    )

    assert result.status == "insufficient_evidence"
    assert result.cited_evidence_ids == ()
    assert "证据不足" in result.text


def test_rejects_empty_evidence_before_llm_call() -> None:
    llm = FakeLLM("不应该调用模型")

    task = ResearchTask(
        task_id="task-empty",
        question="为什么？",
        evidences=(),
    )

    with pytest.raises(
        ValueError,
        match="must contain evidence",
    ):
        asyncio.run(
            AnswerResearchTask(llm).execute(task)
        )

    assert llm.last_request is None
def test_rejects_mixed_valid_and_invalid_citations() -> None:
    llm = FakeLLM(
        "结论 A [E1]，结论 B [E99]。"
    )

    with pytest.raises(
        InvalidGroundedAnswerError,
        match="unknown evidence citation: E99",
    ):
        asyncio.run(
            AnswerResearchTask(llm).execute(sample_task())
        )