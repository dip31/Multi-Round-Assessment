"""
SQLAlchemy ORM models for assessment sessions and rounds.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database.base import Base
from app.models.proctoring import ProctoringEvent
from app.models.advanced_proctoring import AdvancedProctoringEvent


class AssessmentSession(Base):
    """Represents one full assessment attempt by a user.

    Status lifecycle: ``not_started`` → ``in_progress`` → ``completed`` | ``terminated``.
    Columns mirror ``assessment_sessions`` in ``database/schema.sql``.
    """

    __tablename__ = "assessment_sessions"

    id: int = Column(Integer, primary_key=True, index=True)
    user_id: int = Column(Integer, ForeignKey("users.id"), nullable=False)
    status: str = Column(String(20), nullable=False, server_default=text("'not_started'"))
    started_at: datetime = Column(DateTime, server_default=func.now())
    completed_at: Optional[datetime] = Column(DateTime, nullable=True)
    total_score: float = Column(Float, server_default=text("0"))

    # ── Relationships ─────────────────────────────────────────────────
    user = relationship("User", back_populates="assessment_sessions")
    rounds = relationship(
        "AssessmentRound",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="select",
    )
    proctoring_events = relationship(
        "ProctoringEvent",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="select",
    )
    advanced_proctoring_events = relationship(
        "AdvancedProctoringEvent",
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<AssessmentSession id={self.id} status={self.status!r}>"

    @property
    def time_remaining_seconds(self) -> int:
        """Calculate the remaining seconds out of a 30-minute global limit."""
        if not self.started_at:
            return 1800
        # Use simple naive local time to match Postgres timezone-naive func.now() behavior
        now = datetime.now()
        elapsed = (now - self.started_at).total_seconds()
        return max(0, int(1800 - elapsed))


class AssessmentRound(Base):
    """A single round (aptitude / coding / interview) within a session.

    Status lifecycle: ``pending`` → ``active`` → ``completed`` | ``terminated``.
    Columns mirror ``assessment_rounds`` in ``database/schema.sql``.
    """

    __tablename__ = "assessment_rounds"

    id: int = Column(Integer, primary_key=True, index=True)
    session_id: int = Column(
        Integer,
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    round_type: str = Column(String(20), nullable=False)
    status: str = Column(String(20), nullable=False, server_default=text("'pending'"))
    score: float = Column(Float, server_default=text("0"))
    max_questions: int = Column(Integer, nullable=False, server_default=text("20"))
    started_at: datetime = Column(DateTime, server_default=func.now())
    completed_at: Optional[datetime] = Column(DateTime, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────
    session = relationship("AssessmentSession", back_populates="rounds")

    def __repr__(self) -> str:
        return (
            f"<AssessmentRound id={self.id} type={self.round_type!r} "
            f"status={self.status!r}>"
        )
