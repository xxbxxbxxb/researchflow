import asyncio
import json

import pytest

from researchflow.application.use_cases.answer_research_task import (
    AnswerResearchTask,
    GroundedAnswer,
)
from researchflow.application.use_cases.extract_claims import (
    ExtractClaims,
    InvalidClaimExtractionError,
)
from researchflow.application.use_cases.prepare_research_task import (
    EvidenceInput,
    PrepareResearchTask,
)
from researchflow.infrastructure.llm.fake_llm import FakeLLM


def sample_task():
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


def sample_answer():
    return GroundedAnswer(
        task_id="task-001",
        text=(
            "模型采用文本与音频双轴对齐 [E1]；"
            "论文报告了消融实验 [E2]。"
        ),
        cited_evidence_ids=(
            "task-001:E001",
            "task-001:E002",
        ),
        status="answered",
    )


def model_output(claims):
    return json.dumps(
        {"claims": claims},
        ensure_ascii=False,
    )


def test_extracts_claims_with_traceable_evidence_ids():
    llm = FakeLLM(
        model_output([
            {
                "text": "模型采用文本与音频双轴对齐",
                "evidence_aliases": ["E1"],
            },
            {
                "text": "论文报告了消融实验",
                "evidence_aliases": ["E2"],
            },
        ])
    )

    result = asyncio.run(
        ExtractClaims(llm).execute(
            sample_task(),
            sample_answer(),
        )
    )

    assert [
        claim.claim_id
        for claim in result
    ] == [
        "task-001:C001",
        "task-001:C002",
    ]

    assert result[0].evidence_ids == (
        "task-001:E001",
    )

    assert result[1].evidence_ids == (
        "task-001:E002",
    )

    assert result[0].task_id == "task-001"


def test_prompt_contains_answer_and_source_locations():
    llm = FakeLLM(
        model_output([
            {
                "text": "论文报告了消融实验",
                "evidence_aliases": ["E2"],
            }
        ])
    )

    asyncio.run(
        ExtractClaims(llm).execute(
            sample_task(),
            sample_answer(),
        )
    )

    assert llm.last_request is not None

    prompt = llm.last_request.prompt

    assert "双轴对齐有什么作用？" in prompt
    assert "模型采用文本与音频双轴对齐" in prompt
    assert '"alias": "E2"' in prompt
    assert "Experiments, Table 2" in prompt


def test_refusal_returns_no_claims_without_llm_call():
    llm = FakeLLM("should not be called")

    answer = GroundedAnswer(
        task_id="task-001",
        text="证据不足，无法根据当前材料回答。",
        cited_evidence_ids=(),
        status="insufficient_evidence",
    )

    result = asyncio.run(
        ExtractClaims(llm).execute(
            sample_task(),
            answer,
        )
    )

    assert result == ()
    assert llm.last_request is None


def test_rejects_wrong_task_before_llm_call():
    llm = FakeLLM("should not be called")

    answer = GroundedAnswer(
        task_id="task-other",
        text=sample_answer().text,
        cited_evidence_ids=(
            sample_answer().cited_evidence_ids
        ),
        status="answered",
    )

    with pytest.raises(
        ValueError,
        match="different task",
    ):
        asyncio.run(
            ExtractClaims(llm).execute(
                sample_task(),
                answer,
            )
        )

    assert llm.last_request is None


def test_rejects_uncited_but_existing_alias():
    llm = FakeLLM(
        model_output([
            {
                "text": "模型采用文本与音频双轴对齐",
                "evidence_aliases": ["E2"],
            }
        ])
    )

    answer = GroundedAnswer(
        task_id="task-001",
        text="模型采用文本与音频双轴对齐 [E1]。",
        cited_evidence_ids=(
            "task-001:E001",
        ),
        status="answered",
    )

    with pytest.raises(
        InvalidClaimExtractionError,
        match="uncited evidence alias",
    ):
        asyncio.run(
            ExtractClaims(llm).execute(
                sample_task(),
                answer,
            )
        )


def test_rejects_unknown_alias():
    llm = FakeLLM(
        model_output([
            {
                "text": "论文报告了消融实验",
                "evidence_aliases": ["E99"],
            }
        ])
    )

    with pytest.raises(
        InvalidClaimExtractionError,
        match="unknown or uncited",
    ):
        asyncio.run(
            ExtractClaims(llm).execute(
                sample_task(),
                sample_answer(),
            )
        )


def test_rejects_invented_claim_text():
    llm = FakeLLM(
        model_output([
            {
                "text": "这项技术已经完全解决所有问题",
                "evidence_aliases": ["E1"],
            }
        ])
    )

    with pytest.raises(
        InvalidClaimExtractionError,
        match="not in the answer",
    ):
        asyncio.run(
            ExtractClaims(llm).execute(
                sample_task(),
                sample_answer(),
            )
        )


def test_rejects_invalid_json():
    llm = FakeLLM("not JSON")

    with pytest.raises(
        InvalidClaimExtractionError,
        match="invalid JSON",
    ):
        asyncio.run(
            ExtractClaims(llm).execute(
                sample_task(),
                sample_answer(),
            )
        )


def test_rejects_empty_claim_list_for_answered_status():
    llm = FakeLLM('{"claims": []}')

    with pytest.raises(
        InvalidClaimExtractionError,
        match="requires claims",
    ):
        asyncio.run(
            ExtractClaims(llm).execute(
                sample_task(),
                sample_answer(),
            )
        )


def test_full_prepare_answer_extract_pipeline():
    task = sample_task()

    answer_llm = FakeLLM(
        "模型采用文本与音频双轴对齐 [E1]。"
    )

    extract_llm = FakeLLM(
        model_output([
            {
                "text": "模型采用文本与音频双轴对齐",
                "evidence_aliases": ["E1"],
            }
        ])
    )

    async def scenario():
        answer = await AnswerResearchTask(
            answer_llm
        ).execute(task)

        return await ExtractClaims(
            extract_llm
        ).execute(task, answer)

    claims = asyncio.run(scenario())

    assert len(claims) == 1

    assert claims[0].evidence_ids == (
        "task-001:E001",
    )

    assert answer_llm.last_request is not None
    assert extract_llm.last_request is not None