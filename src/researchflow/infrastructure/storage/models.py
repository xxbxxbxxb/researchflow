from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, Text, func, Boolean, BigInteger, Identity, Float
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ProjectRow(Base):
    __tablename__ = 'projects'
    project_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    background: Mapped[str] = mapped_column(Text,default='')


class TaskRow(Base):
    __tablename__ = 'research_tasks'
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.project_id'),primary_key=True)
    task_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    source_ids: Mapped[list[str]] = mapped_column(JSON,default=list)
    parent_task_id: Mapped[str | None] = mapped_column(String(200),nullable=True)
    __table_args__ = (ForeignKeyConstraint(['project_id','parent_task_id'],['research_tasks.project_id','research_tasks.task_id']),)


class SnapshotRow(Base):
    __tablename__ = 'source_snapshots'
    project_id: Mapped[str] = mapped_column(ForeignKey('projects.project_id'),primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    source_uri: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    parser_version: Mapped[str] = mapped_column(String(100))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PageRow(Base):
    __tablename__ = 'snapshot_pages'
    project_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    number: Mapped[int] = mapped_column(Integer,primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    __table_args__ = (ForeignKeyConstraint(['project_id','snapshot_id'],['source_snapshots.project_id','source_snapshots.snapshot_id']),)


class DocumentRow(Base):
    __tablename__ = 'documents'
    project_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    document_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(Text)
    __table_args__ = (ForeignKeyConstraint(['project_id','snapshot_id'],['source_snapshots.project_id','source_snapshots.snapshot_id']),)


class ChunkRow(Base):
    __tablename__ = 'chunks'
    project_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    chunk_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(200))
    page: Mapped[int] = mapped_column(Integer)
    start: Mapped[int] = mapped_column(Integer)
    end: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[Any | None] = mapped_column(Vector(),nullable=True)
    embedding_version: Mapped[str | None] = mapped_column(String(200),nullable=True)
    __table_args__ = (ForeignKeyConstraint(['project_id','snapshot_id','page'],['snapshot_pages.project_id','snapshot_pages.snapshot_id','snapshot_pages.number']),)


class EvidenceRow(Base):
    __tablename__ = 'evidences'
    project_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    evidence_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(String(200))
    page: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict[str,Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),server_default=func.now())
    __table_args__ = (ForeignKeyConstraint(['project_id','snapshot_id','page'],['snapshot_pages.project_id','snapshot_pages.snapshot_id','snapshot_pages.number']),)


class ClaimRow(Base):
    __tablename__ = 'claims'
    project_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    task_id: Mapped[str] = mapped_column(String(200))
    data: Mapped[dict[str,Any]] = mapped_column(JSON)
    __table_args__ = (ForeignKeyConstraint(['project_id','task_id'],['research_tasks.project_id','research_tasks.task_id']),)


class LinkRow(Base):
    __tablename__ = 'claim_evidence_links'
    project_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    evidence_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    relationship: Mapped[str] = mapped_column(String(20),primary_key=True)
    __table_args__ = (ForeignKeyConstraint(['project_id','claim_id'],['claims.project_id','claims.claim_id']),ForeignKeyConstraint(['project_id','evidence_id'],['evidences.project_id','evidences.evidence_id']))


class VerificationRow(Base):
    __tablename__ = 'verifications'
    project_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    verification_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    claim_id: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30))
    data: Mapped[dict[str,Any]] = mapped_column(JSON)
    __table_args__ = (ForeignKeyConstraint(['project_id','claim_id'],['claims.project_id','claims.claim_id']),)


class ReportRow(Base):
    __tablename__ = 'report_versions'
    project_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    report_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    task_id: Mapped[str] = mapped_column(String(200))
    run_id: Mapped[str] = mapped_column(String(200),index=True)
    version: Mapped[int] = mapped_column(Integer)
    data: Mapped[dict[str,Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (ForeignKeyConstraint(['project_id','task_id'],['research_tasks.project_id','research_tasks.task_id']),)


class RunRow(Base):
    __tablename__ = 'workflow_runs'
    project_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    run_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    task_id: Mapped[str] = mapped_column(String(200))
    state: Mapped[str] = mapped_column(String(30),index=True)
    epoch: Mapped[int] = mapped_column(Integer,default=0)
    owner_id: Mapped[str | None] = mapped_column(String(200),nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean,default=False)
    input_version: Mapped[str] = mapped_column(String(200))
    input_manifest: Mapped[dict[str,Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100),nullable=True)
    __table_args__ = (ForeignKeyConstraint(['project_id','task_id'],['research_tasks.project_id','research_tasks.task_id']),)


class StepRow(Base):
    __tablename__ = 'step_receipts'
    project_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    run_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    step_key: Mapped[str] = mapped_column(String(200),primary_key=True)
    output: Mapped[dict[str,Any]] = mapped_column(JSON)
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (ForeignKeyConstraint(['project_id','run_id'],['workflow_runs.project_id','workflow_runs.run_id']),)


class EventRow(Base):
    __tablename__ = 'run_events'
    event_id: Mapped[int] = mapped_column(BigInteger,Identity(),primary_key=True)
    project_id: Mapped[str] = mapped_column(String(200))
    run_id: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(100))
    data: Mapped[dict[str,Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (ForeignKeyConstraint(['project_id','run_id'],['workflow_runs.project_id','workflow_runs.run_id']),)


class SessionRow(Base):
    __tablename__ = 'auth_sessions'
    token_hash: Mapped[str] = mapped_column(String(64),primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(200))
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LoginGuardRow(Base):
    __tablename__ = 'login_guards'
    source_key: Mapped[str] = mapped_column(String(64),primary_key=True)
    window_started: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    failures: Mapped[int] = mapped_column(Integer,default=0)
    pending: Mapped[int] = mapped_column(Integer,default=0)


class IdempotencyRow(Base):
    __tablename__ = 'run_idempotency'
    project_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    request_key: Mapped[str] = mapped_column(String(200),primary_key=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    run_id: Mapped[str] = mapped_column(String(200))
    __table_args__ = (ForeignKeyConstraint(['project_id','run_id'],['workflow_runs.project_id','workflow_runs.run_id']),)


class ReviewRow(Base):
    __tablename__ = 'review_decisions'
    project_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    run_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    decision: Mapped[dict[str,Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (ForeignKeyConstraint(['project_id','run_id'],['workflow_runs.project_id','workflow_runs.run_id']),)


class KnowledgeRow(Base):
    __tablename__ = 'knowledge_entries'
    project_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    knowledge_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    verification_id: Mapped[str] = mapped_column(String(200))
    report_id: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30))
    supersedes_id: Mapped[str | None] = mapped_column(String(200),nullable=True)
    data: Mapped[dict[str,Any]] = mapped_column(JSON)
    __table_args__ = (ForeignKeyConstraint(['project_id','verification_id'],['verifications.project_id','verifications.verification_id']),ForeignKeyConstraint(['project_id','report_id'],['report_versions.project_id','report_versions.report_id']),ForeignKeyConstraint(['project_id','supersedes_id'],['knowledge_entries.project_id','knowledge_entries.knowledge_id']))


class FollowUpRow(Base):
    __tablename__ = 'follow_up_drafts'
    project_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    draft_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    parent_task_id: Mapped[str] = mapped_column(String(200))
    started_run_id: Mapped[str | None] = mapped_column(String(200),nullable=True)
    data: Mapped[dict[str,Any]] = mapped_column(JSON)
    __table_args__ = (ForeignKeyConstraint(['project_id','parent_task_id'],['research_tasks.project_id','research_tasks.task_id']),ForeignKeyConstraint(['project_id','started_run_id'],['workflow_runs.project_id','workflow_runs.run_id']))


class BudgetRow(Base):
    __tablename__ = 'run_budgets'
    project_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    run_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    limits: Mapped[dict[str,Any]] = mapped_column(JSON)
    model_calls_used: Mapped[int] = mapped_column(Integer,default=0)
    tool_calls_used: Mapped[int] = mapped_column(Integer,default=0)
    steps_used: Mapped[int] = mapped_column(Integer,default=0)
    active_elapsed_seconds: Mapped[float] = mapped_column(Float,default=0.0)
    active_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    active_epoch: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean,default=True)
    __table_args__ = (ForeignKeyConstraint(['project_id','run_id'],['workflow_runs.project_id','workflow_runs.run_id']),)


class UsageRow(Base):
    __tablename__ = 'model_usage'
    project_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    run_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    attempt_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    epoch: Mapped[int] = mapped_column(Integer)
    operation: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(40))
    input_tokens: Mapped[int | None] = mapped_column(BigInteger,nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(BigInteger,nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Float,nullable=True)
    price_version: Mapped[str | None] = mapped_column(String(200),nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(200),nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),nullable=True)
    __table_args__ = (ForeignKeyConstraint(['project_id','run_id'],['workflow_runs.project_id','workflow_runs.run_id']),)


class OperationSlotRow(Base):
    __tablename__ = 'operation_slots'
    project_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    run_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    operation_id: Mapped[str] = mapped_column(String(200),primary_key=True)
    epoch: Mapped[int] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (ForeignKeyConstraint(['project_id','run_id'],['workflow_runs.project_id','workflow_runs.run_id']),)
