"""
Additive competency evidence mapping model (Phase 4C Part 4, Stage 2).

This model only records the explicit relationship between a piece of raw
assessment evidence and a competency configured on the blueprint snapshot
that pinned the assessment. It does NOT store any computed competency score;
``raw_metric`` carries the original evidence values untouched.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.database.base import Base


class CompetencyEvidenceMapping(Base):
    """Maps one raw evidence record to one explicitly configured competency.

    A mapping is created only when the evidence's topic exactly matches a topic
    listed under a competency in the session's pinned blueprint snapshot. The
    unique constraint prevents duplicate evidence-to-competency mappings when
    evidence is reprocessed.
    """

    __tablename__ = "competency_evidence_mappings"
    __table_args__ = (
        UniqueConstraint(
            "evidence_type",
            "evidence_id",
            "competency_id",
            name="uq_competency_evidence_mapping",
        ),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    candidate_id: int = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    context_id: int | None = Column(
        Integer,
        ForeignKey("assessment_contexts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    session_id: int = Column(
        Integer,
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    round_id: int = Column(
        Integer,
        ForeignKey("assessment_rounds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_type: str = Column(String(40), nullable=False)  # aptitude_attempt | coding_submission
    evidence_id: int = Column(Integer, nullable=False)
    competency_id: str = Column(String(120), nullable=False)
    competency_name: str = Column(String(200), nullable=False)
    source: str = Column(String(40), nullable=False)  # round_type / evidence origin
    blueprint_version: int | None = Column(Integer, nullable=True)
    raw_metric: dict = Column(JSONB, nullable=False, default=dict)
    created_at: datetime = Column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return (
            f"<CompetencyEvidenceMapping id={self.id} "
            f"evidence_type={self.evidence_type!r} evidence_id={self.evidence_id} "
            f"competency_id={self.competency_id!r}>"
        )
