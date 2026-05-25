"""
SQLAlchemy ORM models for interview round tables.

Maps to the following PostgreSQL tables:
- interview_sessions
- approved_question_pools
- interview_turns
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from shared.db.database import Base


class InterviewSession(Base):
    """Represents an interview session for a candidate.
    
    Columns mirror the ``interview_sessions`` table.
    """

    __tablename__ = "interview_sessions"

    id: int = Column(Integer, primary_key=True, index=True)
    session_id: int = Column(Integer, nullable=False, index=True)  # Removed FK constraint
    phase: str = Column(String(20), server_default="HR", nullable=False)
    current_turn: int = Column(Integer, server_default="0", nullable=False)
    total_turns: int = Column(Integer, server_default="10", nullable=False)
    rl_state: dict = Column(JSON, nullable=True)  # Removed default for SQLite compatibility
    created_at: datetime = Column(DateTime(timezone=False), server_default=func.now(), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────
    turns = relationship(
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

    id: int = Column(Integer, primary_key=True, index=True)
    session_id: int = Column(Integer, nullable=False, index=True)  # Removed FK constraint
    extracted_skills: list = Column(JSON, nullable=True)  # Removed default for SQLite
    extracted_projects: dict = Column(JSON, nullable=True)  # Removed default for SQLite
    question_pool: list = Column(JSON, nullable=False)
    admin_approved: bool = Column(Boolean, server_default=text("false"), nullable=False, index=True)
    approved_by: Optional[int] = Column(Integer, nullable=True)  # Removed FK constraint
    approved_at: Optional[datetime] = Column(DateTime(timezone=False), nullable=True)
    created_at: datetime = Column(DateTime(timezone=False), server_default=func.now(), nullable=True)

    def __repr__(self) -> str:
        return f"<ApprovedQuestionPool id={self.id} session_id={self.session_id} approved={self.admin_approved}>"


class InterviewTurn(Base):
    """Represents a single turn/question in an interview session.
    
    Columns mirror the ``interview_turns`` table.
    """

    __tablename__ = "interview_turns"

    id: int = Column(Integer, primary_key=True, index=True)
    interview_id: int = Column(Integer, ForeignKey("interview_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    turn_number: int = Column(Integer, nullable=False)
    question_text: str = Column(Text, nullable=False)
    question_difficulty: Optional[str] = Column(String(10), nullable=True)
    candidate_response: Optional[str] = Column(Text, nullable=True)
    response_time_sec: Optional[float] = Column(Float, nullable=True)
    content_score: Optional[float] = Column(Float, nullable=True)
    final_score: Optional[float] = Column(Float, nullable=True)
    intent: Optional[str] = Column(String(10), nullable=True)
    behavioral_snapshot: dict = Column(JSON, nullable=True)  # Removed default for SQLite
    rl_reward: Optional[float] = Column(Float, nullable=True)
    is_followup: bool = Column(Boolean, server_default=text("false"), nullable=False)
    followup_number: int = Column(Integer, server_default=text("0"), nullable=False)
    parent_turn_id: Optional[int] = Column(Integer, ForeignKey("interview_turns.id"), nullable=True)
    created_at: datetime = Column(DateTime(timezone=False), server_default=func.now(), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────
    interview = relationship(
        "InterviewSession",
        back_populates="turns",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<InterviewTurn id={self.id} interview_id={self.interview_id} turn={self.turn_number}>"

