from dataclasses import dataclass, field
from typing import Any

from researchflow.domain.knowledge import FollowUpDraft
from researchflow.domain.sources import SourceSnapshot


@dataclass(frozen=True, slots=True)
class ToolCall:
    call_id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    name: str
    data: dict[str, Any] = field(default_factory=dict)
    snapshots: tuple[SourceSnapshot, ...] = ()
    follow_up: FollowUpDraft | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class CollectionResult:
    source_ids: tuple[str, ...]
    insufficient: bool = False
    observations: tuple[ToolResult, ...] = ()
