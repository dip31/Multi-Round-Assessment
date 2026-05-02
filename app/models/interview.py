"""
SQLAlchemy ORM models for interview round tables.

Maps to the following PostgreSQL tables:
- interview_sessions
- approved_question_pools
- interview_turns
"""

from __future__ import annotations

from datetime import datetime

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
    rl_state: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────
    turns: Mapped[list["InterviewTurn"]] = relationship(
        "InterviewTurn",
        back_populates="interview",
        cascade="all, delete-orphan",
        lazy="select",
    )

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
    extracted_skills: Mapped[list] = mapped_column(JSONB, server_default=text("'[]'::jsonb"), nullable=False)
    extracted_projects: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    question_pool: Mapped[list] = mapped_column(JSONB, nullable=False)
    admin_approved: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False, index=True)
    approved_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    detected_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=True)

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
    behavioral_snapshot: Mapped[dict] = mapped_column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
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

    def __repr__(self) -> str:
        return f"<InterviewTurn id={self.id} interview_id={self.interview_id} turn={self.turn_number}>"
