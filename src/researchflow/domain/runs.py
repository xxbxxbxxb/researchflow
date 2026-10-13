from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from researchflow.domain.claims import Claim, Verification
from researchflow.domain.reports import ResearchResult
from researchflow.domain.sources import AnchoredEvidence, SourceSnapshot

RunState = Literal['queued','running','awaiting_review','succeeded','failed','cancelled','interrupted']


@dataclass(frozen=True)
class RunHandle:
    run_id: str
    project_id: str
    task_id: str
    epoch: int
    owner_id: str


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    project_id: str
    task_id: str
    state: RunState
    epoch: int
    owner_id: str | None
    lease_until: datetime | None
    cancel_requested: bool
    input_version: str
    input_manifest: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    error_code: str | None = None


@dataclass(frozen=True)
class StepOutput:
    data: dict[str, Any] = field(default_factory=dict)
    snapshots: tuple[SourceSnapshot, ...] = ()
    evidences: tuple[AnchoredEvidence, ...] = ()
    claims: tuple[Claim, ...] = ()
    verifications: tuple[Verification, ...] = ()
    result: ResearchResult | None = None


@dataclass(frozen=True)
class StepReceipt:
    run_id: str
    step_key: str
    output: StepOutput
    committed_at: datetime


@dataclass(frozen=True)
class RunOutcome:
    state: RunState
    report_id: str | None = None


@dataclass(frozen=True)
class LeaseState:
    handle: RunHandle
    lease_until: datetime


@dataclass(frozen=True)
class ReviewDecision:
    action: Literal['approve','reject']
    actor_id: str
    comment: str = ''
