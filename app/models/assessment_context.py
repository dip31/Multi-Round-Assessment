"""
Assessment Context & Policy models for M2-E.

AssessmentContext: Why does this assessment exist?
AssessmentPolicy: Under what rules does it operate?
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Boolean, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.assessment import AssessmentSession


class AssessmentPolicy(Base):
    """Defines the rules and constraints for assessments.
    
    Backend-authoritative policy enforcement for:
    - Session/round duration
    - Attempt limits
    - Resume/exit permissions
    - Progression mode (independent vs sequential)
    """

    __tablename__ = "assessment_policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    session_duration_minutes: Mapped[int] = mapped_column(Integer, default=180, nullable=False)
    round_duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    max_attempts: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # NULL = unlimited
    resume_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    exit_allowed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    progression_mode: Mapped[str] = mapped_column(
        String(20), default="sequential", nullable=False
    )  # "independent" | "sequential"
    progression_config: Mapped[dict] = mapped_column(
        JSONB, default=dict, nullable=False
    )  # {"rounds": ["aptitude", "coding", "interview"]} for sequential
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    contexts: Mapped[list["AssessmentContext"]] = relationship(
        "AssessmentContext",
        back_populates="policy",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<AssessmentPolicy id={self.id} name={self.name!r}>"


class AssessmentContext(Base):
    """Represents the purpose and configuration of an assessment.
    
    Answers: Why does this assessment session exist?
    Links sessions to their mode (practice/portfolio/mock_drive) and policy.
    """

    __tablename__ = "assessment_contexts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    mode: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # practice | portfolio_verification | mock_drive
    purpose: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Future: practice | reassessment | etc
    created_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True
    )  # TPO/admin who created (for drives)
    student_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=True, index=True
    )  # Student owner (for practice)
    
    # Future fields - placeholders for Mock Drive/Portfolio
    company_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # Placeholder until Company model exists
    target_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    jd_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Placeholder until JD model exists
    
    # Availability window
    availability_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    availability_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Policy
    policy_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("assessment_policies.id"), nullable=False
    )
    
    # Status
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # active | completed | cancelled
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    policy: Mapped["AssessmentPolicy"] = relationship(
        "AssessmentPolicy",
        back_populates="contexts",
        lazy="joined",
    )
    created_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by_id],
        lazy="select",
    )
    student: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[student_id],
        lazy="select",
    )
    sessions: Mapped[list["AssessmentSession"]] = relationship(
        "AssessmentSession",
        back_populates="context",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<AssessmentContext id={self.id} mode={self.mode!r} status={self.status!r}>"
