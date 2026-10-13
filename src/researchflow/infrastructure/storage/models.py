from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, ForeignKey, ForeignKeyConstraint, Integer, String, Text, func, Boolean, BigInteger, Identity
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
