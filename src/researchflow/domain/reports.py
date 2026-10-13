from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from researchflow.domain.claims import Claim, Verification
from researchflow.domain.sources import AnchoredEvidence


@dataclass(frozen=True, slots=True)
class ReportInputs:
    project_id: str
    task_id: str
    run_id: str
    claims: tuple[Claim, ...]
    verifications: tuple[Verification, ...]
    evidences: tuple[AnchoredEvidence, ...]
    unresolved_questions: tuple[str, ...]
    question: str = ''
    execution_mode: Literal['demo', 'live'] = 'live'


@dataclass(frozen=True, slots=True)
class ReportVersion:
    report_id: str
    project_id: str
    task_id: str
    run_id: str
    version: int
    markdown: str
    conclusion_claim_ids: tuple[str, ...]
    finding_claim_ids: tuple[str, ...]
    source_evidence_ids: tuple[str, ...]
    execution_mode: Literal['demo', 'live']
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ResearchResult:
    project_id: str
    task_id: str
    run_id: str
    report: ReportVersion
    claims: tuple[Claim, ...]
    verifications: tuple[Verification, ...]
    evidences: tuple[AnchoredEvidence, ...]
    unresolved_questions: tuple[str, ...]
    execution_mode: Literal['demo', 'live'] = 'live'
