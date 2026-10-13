from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

from researchflow.domain.claims import Claim, Verification
from researchflow.domain.knowledge import KnowledgeEntry
from researchflow.domain.sources import AnchoredEvidence, SourceSnapshot


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


class BudgetInput(StrictInput):
    max_steps: StrictInt=Field(default=12,ge=1,le=12)
    max_tool_calls: StrictInt=Field(default=20,ge=1,le=20)
    max_model_calls: StrictInt=Field(default=16,ge=1,le=16)
    max_concurrency: StrictInt=Field(default=4,ge=1,le=4)
    active_timeout_seconds: float=Field(default=300,gt=0,le=300,allow_inf_nan=False,strict=True)
    operation_timeout_seconds: float=Field(default=60,gt=0,le=60,allow_inf_nan=False,strict=True)


class RunStart(StrictInput):
    project_id: str = Field(min_length=1,max_length=200)
    mode: Literal['demo','live'] | None = None
    driver: Literal['fixed','graph'] = 'fixed'
    collect_sources: bool = False
    limits: BudgetInput | None = None
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
    preview_enabled: bool = False


class RunEventResponse(BaseModel):
    event_id: int
    run_id: str
    kind: str
    data: dict[str,Any]
    created_at: datetime


class PhaseMetric(BaseModel):
    step_id: str
    elapsed_since_previous_seconds: float | None


class RunMetricsResponse(BaseModel):
    phases: list[PhaseMetric]
    model_attempts: int
    retries: int
    recoveries: int
    usage_known: bool
    estimated_cost: float | None
    verification_distribution: dict[str,int]
    citation_coverage: float | None
