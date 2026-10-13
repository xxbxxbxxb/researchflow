from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class KnowledgeEntry:
    knowledge_id: str
    project_id: str
    verification_id: str
    report_id: str
    accepted_by: str
    accepted_at: datetime
    status: Literal['active','superseded'] = 'active'
    supersedes_id: str | None = None


@dataclass(frozen=True)
class FollowUpDraft:
    draft_id: str
    project_id: str
    parent_task_id: str
    question: str
    claim_ids: tuple[str,...]
    started_run_id: str | None = None
