"""
SQLAlchemy ORM models for interview round tables.

Maps to the following PostgreSQL tables:
- interview_sessions
- approved_question_pools
- interview_turns
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database.base import Base


class InterviewSession(Base):
    """Represents an interview session for a candidate.
    
    Columns mirror the ``interview_sessions`` table.
    """

    __tablename__ = "interview_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phase: Mapped[str] = mapped_column(String(20), server_default="HR", nullable=False)
    current_turn: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    total_turns: Mapped[int] = mapped_column(Integer, server_default="10", nullable=False)
    rl_state: Mapped[Dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="ACTIVE", nullable=False)
    completion_reason: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # ALL_QUESTIONS_COMPLETED | USER_SUBMITTED | TIME_EXPIRED
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────
    turns: Mapped[list["InterviewTurn"]] = relationship(
        "InterviewTurn",
        back_populates="interview",
        cascade="all, delete-orphan",
        lazy="select",
    )

    @property
    def rl_state_dict(self) -> Dict[str, Any]:
        """Get rl_state as a dict."""
        return self.rl_state or {}

    @rl_state_dict.setter
    def rl_state_dict(self, value: Dict[str, Any]) -> None:
        """Set rl_state from a dict."""
        self.rl_state = value

    def __repr__(self) -> str:
        return f"<InterviewSession id={self.id} session_id={self.session_id} phase={self.phase!r}>"


class ApprovedQuestionPool(Base):
    """Represents an approved question pool for an interview.
    
    Columns mirror the ``approved_question_pools`` table.
    """

    __tablename__ = "approved_question_pools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extracted_skills: Mapped[List[str]] = mapped_column(JSONB, server_default=text("'[]'"), nullable=False)
    extracted_projects: Mapped[Dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"), nullable=False)
    question_pool: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    admin_approved: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False, index=True)
    approved_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    detected_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=True)

    @property
    def extracted_skills_list(self) -> List[str]:
        return self.extracted_skills or []

    @extracted_skills_list.setter
    def extracted_skills_list(self, value: List[str]) -> None:
        self.extracted_skills = value

    @property
    def extracted_projects_dict(self) -> Dict[str, Any]:
        return self.extracted_projects or {}

    @extracted_projects_dict.setter
    def extracted_projects_dict(self, value: Dict[str, Any]) -> None:
        self.extracted_projects = value

    @property
    def question_pool_list(self) -> List[Dict[str, Any]]:
        return self.question_pool or []

    @question_pool_list.setter
    def question_pool_list(self, value: List[Dict[str, Any]]) -> None:
        self.question_pool = value

    def __repr__(self) -> str:
        return f"<ApprovedQuestionPool id={self.id} session_id={self.session_id} approved={self.admin_approved}>"


class InterviewTurn(Base):
    """Represents a single turn/question in an interview session.
    
    Columns mirror the ``interview_turns`` table.
    """

    __tablename__ = "interview_turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    interview_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_difficulty: Mapped[str | None] = mapped_column(String(10), nullable=True)
    candidate_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_time_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    content_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    intent: Mapped[str | None] = mapped_column(String(10), nullable=True)
    behavioral_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"), nullable=False)
    rl_reward: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_followup: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    followup_number: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    parent_turn_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("interview_turns.id"), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────
    interview: Mapped["InterviewSession"] = relationship(
        "InterviewSession",
        back_populates="turns",
        lazy="select",
    )

    @property
    def behavioral_snapshot_dict(self) -> Dict[str, Any]:
        return self.behavioral_snapshot or {}

    @behavioral_snapshot_dict.setter
    def behavioral_snapshot_dict(self, value: Dict[str, Any]) -> None:
        self.behavioral_snapshot = value

    def __repr__(self) -> str:
        return f"<InterviewTurn id={self.id} interview_id={self.interview_id} turn={self.turn_number}>"


class ProctoringViolation(Base):
    """Represents a proctoring violation detected during an interview session.
    
    Columns mirror the ``proctoring_violations`` table.
    """

    __tablename__ = "proctoring_violations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    face_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    violation_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=True,
    )

    @property
    def metadata_dict(self) -> Optional[Dict[str, Any]]:
        return self.violation_metadata

    @metadata_dict.setter
    def metadata_dict(self, value: Optional[Dict[str, Any]]) -> None:
        self.violation_metadata = value

    def __repr__(self) -> str:
        return f"<ProctoringViolation id={self.id} session_id={self.session_id} event_type={self.event_type!r}>"
