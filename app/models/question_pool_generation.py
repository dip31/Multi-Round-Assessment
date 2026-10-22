"""LLM-generated question pool registry.

Blueprint-scoped pool bookkeeping for role-specific (LLM-generated) assessments.

One row per (blueprint_id, blueprint_version, round_type). The pool's executable
content lives in the existing per-round storage:
- aptitude            -> aptitude_topics / aptitude_questions rows
- coding              -> coding_problems / coding_test_cases rows
- technical_interview -> content JSONB (question dicts, same shape as
                         ApprovedQuestionPool.question_pool) so the existing
                         interview turn engine can consume it unchanged
- hr_interview        -> content JSONB (same shape, phase=HR)

``status`` lifecycle: pending -> in_progress -> complete | incomplete | failed.
A pool is only marked complete when the full pool validated and was persisted.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


# Valid round types that a generated pool can cover.
GENERATED_POOL_ROUNDS = (
    "aptitude",
    "coding",
    "technical_interview",
    "hr_interview",
)

# Fixed pool sizes (Part C hard requirements).
POOL_SIZES = {
    "aptitude": 30,
    "coding": 10,
    "technical_interview": 10,
    "hr_interview": 10,
}

# Bounded provider batching: no single LLM call asks for more than this many
# items. A pool of N is generated as batches of this size (the final batch
# carries any remainder), then concatenated, de-duplicated, and validated
# against the FULL pool spec.
POOL_BATCH_SIZES = {
    "aptitude": 10,
    "coding": 5,
    "technical_interview": 5,
    "hr_interview": 5,
}

# Status values.
POOL_STATUS_PENDING = "pending"
POOL_STATUS_IN_PROGRESS = "in_progress"
POOL_STATUS_COMPLETE = "complete"
POOL_STATUS_INCOMPLETE = "incomplete"
POOL_STATUS_FAILED = "failed"


class GeneratedQuestionPool(Base):
    """Registry + validated content for a blueprint-scoped generated pool."""

    __tablename__ = "generated_question_pools"
    __table_args__ = (
        UniqueConstraint(
            "blueprint_id",
            "blueprint_version",
            "round_type",
            name="uq_generated_pool_blueprint_version_round",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ── Blueprint / version isolation ────────────────────────────────
    blueprint_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("company_blueprints.id", ondelete="CASCADE"), nullable=False, index=True
    )
    blueprint_version: Mapped[int] = mapped_column(Integer, nullable=False)
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_role: Mapped[str] = mapped_column(String(150), nullable=False)

    # aptitude | coding | technical_interview | hr_interview
    round_type: Mapped[str] = mapped_column(String(30), nullable=False)

    # pending | in_progress | complete | incomplete | failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=POOL_STATUS_PENDING)

    # ── Generation / batch identity ──────────────────────────────────
    batch_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    required_count: Mapped[int] = mapped_column(Integer, nullable=False)
    validated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    generation_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Executable content for interview-style rounds (list of question dicts
    # compatible with ApprovedQuestionPool.question_pool). Aptitude/coding
    # pools persist real rows in their own tables and leave this NULL.
    content: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # ── Ownership ─────────────────────────────────────────────────────
    created_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    blueprint = relationship(
        "CompanyBlueprint", lazy="select", foreign_keys=[blueprint_id]
    )

    def __repr__(self) -> str:
        return (
            f"<GeneratedQuestionPool id={self.id} bp={self.blueprint_id} "
            f"v={self.blueprint_version} round={self.round_type!r} "
            f"status={self.status!r} {self.validated_count}/{self.required_count}>"
        )
