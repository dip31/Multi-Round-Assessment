"""
ORM model for asynchronous resume processing jobs (Stage 6 backend prep).

This table tracks a single in-flight background job that:
    1. reads a resume file already stored in object storage (``storage_key``)
    2. parses the resume (RAG / NLP)
    3. builds and persists the ApprovedQuestionPool for the interview round

The HTTP layer (FastAPI endpoint) inserts a row with status=PENDING, uploads
the bytes to the StorageClient (MinIO in production), and enqueues a Celery
task that carries ONLY ``job_id`` + ``storage_key`` — never the raw bytes.

Why a dedicated table:
- Decouples HTTP from job lifecycle so the frontend can poll status without
  re-running parse logic.
- Survives Celery / Redis restarts (the worker reads pending jobs on retry).
- Gives us retry_count + error_message for observability and idempotency.

NOTE: This file ONLY defines the table and the model. No business code, no
endpoint, and no Celery task is wired to it yet — that happens in Stage 6
under explicit review/approval. The synchronous resume-upload endpoint
remains untouched and continues to work.

Status lifecycle (controlled string, not a real PG enum to allow easy
additions without migrations later):
    PENDING    : Job created, not yet claimed by a worker
    PROCESSING : Worker claimed the job and started parsing
    COMPLETED  : Parsed; ApprovedQuestionPool created and ready for interview
    FAILED     : Exhausted retries or unrecoverable error (see error_message)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database.base import Base


class ResumeProcessingJob(Base):
    """Background resume parsing job record (Stage 6 backend prep).

    Schema mirrors the same column names in ``resume_processing_jobs``;
    see ``add_resume_processing_jobs`` Alembic migration for DDL.
    """

    __tablename__ = "resume_processing_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Object-store key (bucket+key) where theuploaded resume lives.
    # Required on insert so even a future "retry on a stuck job" path knows
    # where to fetch the bytes from without touching HTTP state.
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    original_filename: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Controlled enum-like string. Not a PG ENUM so new states don't force
    # a migration. See module docstring for valid values.
    status: Mapped[str] = mapped_column(
        String(20), server_default=text("'PENDING'"), nullable=False, index=True
    )
    # Free-text progress / step identifier ("uploading_minio",
    # "parsing_resume", "generating_pool", "done"). Surplus detail beyond
    # the coarse status — supports a future progress bar without schema churn.
    progress_step: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(
        Integer, server_default=text("0"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), nullable=True, index=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=False), nullable=True)

    # ── Optional structured metadata for diagnostics ───────────────────
    # e.g. extracted_skills count, parse latency, detected role. Stored as
    # JSONB (default ``{}``) so future add-fields don't require a migration.
    job_metadata: Mapped[Optional[dict]] = mapped_column(
        JSONB, server_default=text("'{}'"), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<ResumeProcessingJob id={self.id} user_id={self.user_id} "
            f"session_id={self.session_id} status={self.status!r}>"
        )
