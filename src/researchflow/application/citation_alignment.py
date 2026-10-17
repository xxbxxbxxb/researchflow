"""Deterministic validation of claim-to-citation alignment."""

import re
from collections.abc import Sequence


# Citation syntax / 引用语法
# 支持 [E1]、[E1][E2]、[E1] [E2]
_CITATION_BLOCK = re.compile(
    r"(?:[ \t]*\[E[1-9]\d*\])+"
)

# Citation token / 单个引用标记
_CITATION_TOKEN = re.compile(
    r"\[(E[1-9]\d*)\]"
)

# Adjacent bracket / 紧邻的左方括号
_ADJACENT_BRACKET = re.compile(
    r"[ \t]*\["
)


def require_citation_alignment(
    answer_text: str,
    claim_text: str,
    aliases: Sequence[str],
) -> None:
    """Require a unique claim followed by exactly its citations."""

    # Locate claim / 定位 Claim 原文
    start = answer_text.find(claim_text)

    # Reject ambiguity / 拒绝重复或不存在的 Claim
    if (
        start < 0
        or answer_text.find(
            claim_text,
            start + 1,
        ) >= 0
    ):
        raise ValueError(
            "claim text must occur exactly once in the answer"
        )

    # Inspect suffix / 读取 Claim 后面的内容
    suffix = answer_text[
        start + len(claim_text):
    ]

    # Match citations / 匹配紧邻引用块
    block = _CITATION_BLOCK.match(suffix)

    if block is None:
        raise ValueError(
            "claim must be immediately followed by citation markers"
        )

    # Reject malformed adjacent citations
    # 拒绝没有被合法匹配的紧邻方括号块
    remainder = suffix[block.end():]

    if _ADJACENT_BRACKET.match(remainder):
        raise ValueError(
            "malformed adjacent citation marker"
        )

    # Extract citations / 提取原文中的引用
    expected = set(
        _CITATION_TOKEN.findall(
            block.group()
        )
    )

    # Compare membership / 比较引用集合
    if set(aliases) != expected:
        raise ValueError(
            "claim citation aliases do not match answer"
        )