"""
SQLAlchemy ORM models for Portfolio Builder Assessment.

Provides orchestration layer over existing assessment systems:
- PortfolioBuilderAttempt: Parent record tracking the 6-stage journey
- PortfolioBuilderStage: Individual stage state and evidence links
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional
from enum import Enum as PyEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.assessment import AssessmentSession, AssessmentRound
    from app.models.interview import InterviewSession


class PortfolioBuilderStageKey(str, PyEnum):
    """Canonical stage keys for the 6 mandatory stages in order."""
    APTITUDE = "APTITUDE"
    TECHNICAL_MCQ = "TECHNICAL_MCQ"
    COMBINED_MCQ = "COMBINED_MCQ"
    DSA_CODING = "DSA_CODING"
    RESUME_INTERVIEW = "RESUME_INTERVIEW"
    COMPETENCY_RESULTS = "COMPETENCY_RESULTS"


class PortfolioBuilderStageStatus(str, PyEnum):
    """Stage lifecycle status."""
    LOCKED = "LOCKED"
    AVAILABLE = "AVAILABLE"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class PortfolioBuilderAttemptStatus(str, PyEnum):
    """Overall attempt lifecycle status."""
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    ABANDONED = "ABANDONED"


class PortfolioBuilderAttempt(Base):
    """
    Parent orchestration record for a student's Portfolio Builder journey.
    
    One attempt per student (under current business rules). Tracks overall
    progress through the 6 mandatory stages.
    """
    
    __tablename__ = "portfolio_builder_attempts"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    
    # Current progress
    current_stage: Mapped[str] = mapped_column(
        String(30), nullable=False, server_default=text("'APTITUDE'")
    )
    overall_status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'ACTIVE'")
    )
    
    # Configuration reference (links to assessment context/policy if needed)
    config_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Concurrency control
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    
    # ── Relationships ─────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="portfolio_builder_attempt")
    stages: Mapped[list["PortfolioBuilderStage"]] = relationship(
        "PortfolioBuilderStage",
        back_populates="attempt",
        cascade="all, delete-orphan",
        lazy="select",
        order_by="PortfolioBuilderStage.sequence",
    )
    
    def __repr__(self) -> str:
        return f"<PortfolioBuilderAttempt id={self.id} user_id={self.user_id} stage={self.current_stage} status={self.overall_status}>"


class PortfolioBuilderStage(Base):
    """
    Individual stage record within a Portfolio Builder attempt.
    
    Links to the underlying assessment attempt/round/interview session
    that provides the actual evidence for this stage.
    """
    
    __tablename__ = "portfolio_builder_stages"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    attempt_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("portfolio_builder_attempts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Stage identification
    stage_key: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Stage status
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'LOCKED'")
    )
    
    # Links to underlying assessment evidence
    # For MCQ stages (1, 2, 3): links to AssessmentRound
    assessment_round_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("assessment_rounds.id", ondelete="SET NULL"), nullable=True, index=True
    )
    # For coding stage (4): links to AssessmentRound (coding type)
    # For interview stage (5): links to InterviewSession
    interview_session_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("interview_sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    
    # Stage result snapshot (denormalized for quick access)
    score: Mapped[Optional[float]] = mapped_column(nullable=True)  # 0-100 or 0-1 scaled
    max_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    passed: Mapped[Optional[bool]] = mapped_column(nullable=True)
    
    # Failure/recovery info (safe to expose to student)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    
    # Timestamps
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # ── Relationships ─────────────────────────────────────────────────
    attempt: Mapped["PortfolioBuilderAttempt"] = relationship("PortfolioBuilderAttempt", back_populates="stages")
    assessment_round: Mapped[Optional["AssessmentRound"]] = relationship("AssessmentRound", lazy="select")
    interview_session: Mapped[Optional["InterviewSession"]] = relationship("InterviewSession", lazy="select")
    
    # Composite unique constraint: one stage per attempt per stage_key
    __table_args__ = (
        UniqueConstraint("attempt_id", "stage_key", name="uq_portfolio_builder_stage_attempt_key"),
    )
    
    def __repr__(self) -> str:
        return f"<PortfolioBuilderStage id={self.id} attempt_id={self.attempt_id} key={self.stage_key} status={self.status}>"