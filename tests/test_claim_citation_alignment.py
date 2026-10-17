import asyncio
import json

import pytest

from researchflow.application.use_cases.answer_research_task import (
    GroundedAnswer,
)
from researchflow.application.use_cases.extract_claims import (
    ExtractClaims,
    InvalidClaimExtractionError,
)
from researchflow.domain.research import (
    Evidence,
    ResearchTask,
)
from researchflow.infrastructure.llm.fake_llm import (
    FakeLLM,
)


def run_case(
    answer_text: str,
    claims: list[dict],
    cited: tuple[str, ...] = (
        "task-001:E001",
        "task-001:E002",
    ),
):
    # Prepare task / 准备科研任务
    task = ResearchTask(
        task_id="task-001",
        question="双轴对齐有什么作用？",
        evidences=(
            Evidence(
                "task-001:E001",
                "paper",
                "Section 1",
                "第一条证据",
            ),
            Evidence(
                "task-001:E002",
                "paper",
                "Section 2",
                "第二条证据",
            ),
        ),
    )

    # Prepare answer / 准备回答
    answer = GroundedAnswer(
        task_id="task-001",
        text=answer_text,
        cited_evidence_ids=cited,
        status="answered",
    )

    # Fake LLM / 模拟模型输出
    llm = FakeLLM(
        json.dumps(
            {"claims": claims},
            ensure_ascii=False,
        )
    )

    return asyncio.run(
        ExtractClaims(llm).execute(
            task,
            answer,
        )
    )


def test_correct_alignment():
    result = run_case(
        "结论甲 [E1]；结论乙 [E2]。",
        [
            {
                "text": "结论甲",
                "evidence_aliases": ["E1"],
            },
            {
                "text": "结论乙",
                "evidence_aliases": ["E2"],
            },
        ],
    )

    assert [
        claim.evidence_ids
        for claim in result
    ] == [
        ("task-001:E001",),
        ("task-001:E002",),
    ]


def test_swapped_existing_alias_is_rejected():
    with pytest.raises(
        InvalidClaimExtractionError,
        match="do not match",
    ):
        run_case(
            "结论甲 [E1]；结论乙 [E2]。",
            [
                {
                    "text": "结论甲",
                    "evidence_aliases": ["E2"],
                }
            ],
        )


def test_multi_citation_deduplicates():
    result = run_case(
        "综合结论 [E1][E2]。",
        [
            {
                "text": "综合结论",
                "evidence_aliases": [
                    "E2",
                    "E1",
                    "E1",
                ],
            }
        ],
    )

    assert result[0].evidence_ids == (
        "task-001:E002",
        "task-001:E001",
    )


def test_repeated_claim_text_is_rejected():
    with pytest.raises(
        InvalidClaimExtractionError,
        match="exactly once",
    ):
        run_case(
            "结论甲 [E1]；结论甲 [E2]。",
            [
                {
                    "text": "结论甲",
                    "evidence_aliases": ["E1"],
                }
            ],
        )


def test_nonadjacent_citation_is_rejected():
    with pytest.raises(
        InvalidClaimExtractionError,
        match="immediately followed",
    ):
        run_case(
            "结论甲，因此可以得到 [E1]。",
            [
                {
                    "text": "结论甲",
                    "evidence_aliases": ["E1"],
                }
            ],
        )


def test_malformed_adjacent_citation_is_rejected():
    with pytest.raises(
        InvalidClaimExtractionError,
        match="malformed adjacent",
    ):
        run_case(
            "综合结论 [E1][E2x]。",
            [
                {
                    "text": "综合结论",
                    "evidence_aliases": ["E1"],
                }
            ],
        )