from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Any
from researchflow.domain.sources import AnchoredEvidence,SourceSnapshot
from researchflow.domain.claims import Claim,Verification
from researchflow.domain.knowledge import KnowledgeEntry


class StrictInput(BaseModel):
    model_config = ConfigDict(extra='forbid',str_strip_whitespace=True)


class LoginInput(StrictInput):
    model_config = ConfigDict(extra='forbid')
    password: str = Field(min_length=1,max_length=1024,repr=False)


class ProjectInput(StrictInput):
    name: str = Field(min_length=1,max_length=200)
    background: str = Field(default='',max_length=10000)


class TaskInput(StrictInput):
    question: str = Field(min_length=1,max_length=5000)
    source_ids: list[str] = Field(default_factory=list,max_length=100)
    parent_task_id: str | None = None


class RunStart(StrictInput):
    project_id: str = Field(min_length=1,max_length=200)
    mode: Literal['demo','live'] | None = None
    driver: Literal['fixed'] = 'fixed'
    require_review: bool = False
    demo_case: Literal['supported','contradicted','insufficient','invalid-citation'] = 'supported'


class URLInput(StrictInput):
    url: str = Field(min_length=1,max_length=5000)


class ResumeInput(StrictInput):
    input_version: str | None = None


class ReviewInput(StrictInput):
    action: Literal['approve','reject']
    comment: str = Field(default='',max_length=2000)


class EvidenceBundle(BaseModel):
    evidence: AnchoredEvidence
    snapshot: SourceSnapshot


class KnowledgeRecordResponse(BaseModel):
    entry: KnowledgeEntry
    claim: Claim
    verification: Verification
    evidences: tuple[AnchoredEvidence,...]
    replacement_candidates: tuple[Verification,...]


class AuthSessionResponse(BaseModel):
    actor_id: str
    csrf_token: str
    execution_mode: Literal['demo','live']


class RunEventResponse(BaseModel):
    event_id: int
    run_id: str
    kind: str
    data: dict[str,Any]
    created_at: datetime
