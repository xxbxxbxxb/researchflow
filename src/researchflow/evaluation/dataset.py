import json
from dataclasses import dataclass
from hashlib import sha256
from importlib.resources import files
from typing import Literal


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    claim_id: int
    doc_id: int
    claim: str
    abstract: tuple[str,...]
    title: str
    gold: Literal['supported','contradicted','insufficient']
    evidence_sentences: tuple[int,...]
    source_split: str
    source_hash: str
    document_hash: str
    tags: tuple[str,...]=()


@dataclass(frozen=True)
class Prediction:
    case_id: str
    gold: str
    predicted: str
    accepted_evidence_ids: tuple[str,...]=()
    provided_evidence_ids: tuple[str,...]=()
    error_code: str | None=None


@dataclass(frozen=True)
class Metrics:
    total: int
    completed: int
    supported_precision: float | None
    supported_recall: float | None
    accuracy: float | None
    evidence_coverage: float | None
    confusion_matrix: dict[str,dict[str,int]]
    unsupported_as_supported: tuple[str,...]


@dataclass(frozen=True)
class EvaluationReport:
    status: str
    mode: str
    quality_measured: bool
    total_cases: int
    predictions: tuple[Prediction,...]
    metrics: Metrics | None
    metadata: dict


def validate_splits(development,holdout):
    if {c.claim_id for c in development}&{c.claim_id for c in holdout} or {c.doc_id for c in development}&{c.doc_id for c in holdout}:
        raise ValueError('development and holdout must not share claims or documents')
    for group in (development,holdout):
        if len({c.case_id for c in group})!=len(group) or len({c.doc_id for c in group})!=len(group):
            raise ValueError('evaluation cases must be independent')


def load_split(split):
    if split not in ('development','holdout'):
        raise ValueError('unknown evaluation split')
    root=files('researchflow.evaluation').joinpath('data')
    data=root.joinpath(split+'.jsonl').read_bytes()
    manifest=json.loads(root.joinpath('manifest.json').read_text())
    if sha256(data).hexdigest()!=manifest['splits'][split]['sha256']:
        raise ValueError('evaluation dataset hash mismatch')
    cases=[]
    for line in data.splitlines():
        item=json.loads(line)
        for key in ('abstract','evidence_sentences','tags'):
            item[key]=tuple(item[key])
        cases.append(EvalCase(**item))
    return tuple(cases)
