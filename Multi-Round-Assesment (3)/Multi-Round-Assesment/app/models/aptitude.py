"""
SQLAlchemy ORM models for aptitude round tables.

Maps to the following PostgreSQL tables:
- aptitude_topics
- aptitude_questions
- aptitude_attempts
- rl_sessions
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.base import Base


class AptitudeTopic(Base):
    """Represents a topic category for aptitude questions.

    Columns mirror the ``aptitude_topics`` table in ``database/schema.sql``.
    """

    __tablename__ = "aptitude_topics"

    id: int = Column(Integer, primary_key=True, index=True)
    name: str = Column(String(100), unique=True, nullable=False)

    # ── Relationships ─────────────────────────────────────────────────
    questions = relationship(
        "AptitudeQuestion",
        back_populates="topic",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<AptitudeTopic id={self.id} name={self.name!r}>"


class AptitudeQuestion(Base):
    """Represents an aptitude MCQ question with difficulty level.

    Columns mirror the ``aptitude_questions`` table in ``database/schema.sql``.
    """

    __tablename__ = "aptitude_questions"

    id: int = Column(Integer, primary_key=True, index=True)
    question_text: str = Column(Text, nullable=False)
    option_a: str = Column(Text, nullable=False)
    option_b: str = Column(Text, nullable=False)
    option_c: str = Column(Text, nullable=False)
    option_d: str = Column(Text, nullable=False)
    correct_option: str = Column(String(1), nullable=False)
    difficulty: str = Column(String(10), nullable=False, index=True)
    topic_id: Optional[int] = Column(Integer, ForeignKey("aptitude_topics.id"), nullable=True)
    version: int = Column(Integer, nullable=False, server_default=text("1"))
    is_active: bool = Column(Boolean, nullable=False, server_default=text("true"))
    created_by: Optional[int] = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: datetime = Column(DateTime, server_default=func.now())

    # ── Relationships ─────────────────────────────────────────────────
    topic = relationship("AptitudeTopic", back_populates="questions")
    attempts = relationship(
        "AptitudeAttempt",
        back_populates="question",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<AptitudeQuestion id={self.id} difficulty={self.difficulty!r}>"


class AptitudeAttempt(Base):
    """Records a single question attempt within an aptitude round.

    Columns mirror the ``aptitude_attempts`` table in ``database/schema.sql``.
    """

    __tablename__ = "aptitude_attempts"

    id: int = Column(Integer, primary_key=True, index=True)
    round_id: int = Column(
        Integer,
        ForeignKey("assessment_rounds.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: int = Column(Integer, ForeignKey("aptitude_questions.id"), nullable=False)
    attempt_number: int = Column(Integer, nullable=False)
    selected_option: Optional[str] = Column(String(1), nullable=True)
    is_correct: Optional[bool] = Column(Boolean, nullable=True)
    response_time: Optional[float] = Column(Float, nullable=True)
    difficulty: Optional[str] = Column(String(10), nullable=True)
    reward: Optional[float] = Column(Float, nullable=True)
    attempted_at: datetime = Column(DateTime, server_default=func.now())

    # ── Relationships ─────────────────────────────────────────────────
    question = relationship("AptitudeQuestion", back_populates="attempts")

    def __repr__(self) -> str:
        return (
            f"<AptitudeAttempt id={self.id} round_id={self.round_id} "
            f"is_correct={self.is_correct}>"
        )


class RLSession(Base):
    """Tracks reinforcement learning state for adaptive difficulty.

    Columns mirror the ``rl_sessions`` table in ``database/schema.sql``.
    """

    __tablename__ = "rl_sessions"

    id: int = Column(Integer, primary_key=True, index=True)
    round_id: int = Column(
        Integer,
        ForeignKey("assessment_rounds.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_number: int = Column(Integer, nullable=False)
    prev_difficulty: Optional[str] = Column(String(10), nullable=True)
    action_taken: str = Column(String(10), nullable=False)
    reward_received: Optional[float] = Column(Float, nullable=True)
    accuracy_so_far: Optional[float] = Column(Float, nullable=True)
    avg_response_time: Optional[float] = Column(Float, nullable=True)
    q_values: Optional[dict] = Column(JSONB, nullable=True)
    created_at: datetime = Column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return (
            f"<RLSession id={self.id} round_id={self.round_id} "
            f"step={self.step_number}>"
        )
