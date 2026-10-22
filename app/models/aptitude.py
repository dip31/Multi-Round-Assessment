"""
SQLAlchemy ORM models for aptitude round tables.

Maps to the following PostgreSQL tables:
- aptitude_topics
- aptitude_questions
- aptitude_attempts
- rl_sessions
"""

from datetime import datetime
from typing import Optional, Dict, Any
import json

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.base import Base


def json_serializer(value: Optional[Dict[str, Any]]) -> Optional[str]:
    """Serialize dict to JSON string."""
    return json.dumps(value) if value is not None else None


def json_deserializer(value: Optional[str], default: Any = None) -> Any:
    """Deserialize JSON string to dict."""
    if value is None:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


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

    # ── Generated-content provenance / blueprint scoping (additive) ──
    # source is NULL for seeded rows, 'llm_generated' for generated rows.
    source: Optional[str] = Column(String(30), nullable=True)
    source_batch: Optional[str] = Column(String(64), nullable=True)
    company_name: Optional[str] = Column(String(200), nullable=True)
    target_role: Optional[str] = Column(String(150), nullable=True)
    blueprint_id: Optional[int] = Column(
        Integer,
        ForeignKey("company_blueprints.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    blueprint_version: Optional[int] = Column(Integer, nullable=True)

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


class AptitudeRoundQuestion(Base):
    """Pinned question assignments for an aptitude assessment round."""

    __tablename__ = "aptitude_round_questions"
    __table_args__ = (
        UniqueConstraint("round_id", "question_id", name="uq_aptitude_round_question"),
        UniqueConstraint("round_id", "question_order", name="uq_aptitude_round_question_order"),
    )

    id: int = Column(Integer, primary_key=True, index=True)
    round_id: int = Column(
        Integer,
        ForeignKey("assessment_rounds.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: int = Column(
        Integer,
        ForeignKey("aptitude_questions.id"),
        nullable=False,
    )
    question_order: int = Column(Integer, nullable=False)
    assigned_at: datetime = Column(DateTime, nullable=False, server_default=func.now())
    question = relationship("AptitudeQuestion")


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
    q_values: Optional[str] = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime, server_default=func.now())

    @property
    def q_values_dict(self) -> Optional[Dict[str, Any]]:
        return json_deserializer(self.q_values)

    @q_values_dict.setter
    def q_values_dict(self, value: Optional[Dict[str, Any]]) -> None:
        self.q_values = json_serializer(value)

    def __repr__(self) -> str:
        return (
            f"<RLSession id={self.id} round_id={self.round_id} "
            f"step={self.step_number}>"
        )
