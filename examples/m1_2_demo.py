"""M1.2: ResearchTask -> Answer -> Claims demo."""

import asyncio
import json

from researchflow.application.use_cases.answer_research_task import (
    AnswerResearchTask,
)
from researchflow.application.use_cases.extract_claims import (
    ExtractClaims,
)
from researchflow.application.use_cases.prepare_research_task import (
    EvidenceInput,
    PrepareResearchTask,
)
from researchflow.infrastructure.llm.fake_llm import (
    FakeLLM,
)


async def main() -> None:
    # 第一步：准备科研任务与证据
    task = PrepareResearchTask().execute(
        task_id="task-demo",
        question="双轴对齐有什么作用？",
        items=[
            EvidenceInput(
                source="paper:EEGAlign",
                locator="Methods, Section 3",
                text="模型分别对齐 EEG 与文本、音频特征。",
            ),
        ],
    )

    # 第二步：生成带引用的研究回答
    answer_llm = FakeLLM(
        "模型采用文本与音频双轴对齐 [E1]。"
    )

    answer = await AnswerResearchTask(
        answer_llm
    ).execute(task)

    # 第三步：模拟 Claim 提取模型的 JSON 输出
    fake_claim_json = json.dumps(
        {
            "claims": [
                {
                    "text": "模型采用文本与音频双轴对齐",
                    "evidence_aliases": ["E1"],
                }
            ]
        },
        ensure_ascii=False,
    )

    extract_llm = FakeLLM(
        fake_claim_json
    )

    # 第四步：将回答转换为结构化 Claim
    claims = await ExtractClaims(
        extract_llm
    ).execute(task, answer)

    print("answer:", answer.text)

    for claim in claims:
        print(
            "claim:",
            claim.claim_id,
            claim.text,
            claim.evidence_ids,
        )


if __name__ == "__main__":
    asyncio.run(main())