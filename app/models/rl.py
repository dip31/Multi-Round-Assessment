"""
SQLAlchemy ORM models for RL Engine tables.

Maps to:
- rl_q_table      — per-user Q-values for adaptive difficulty
- rl_attempt_log   — full audit trail for debugging and DQN replay
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.database.base import Base


class RLQTable(Base):
    """Stores per-user Q-table values, persisted across sessions.

    Composite primary key: ``(user_id, state, action)``.
    """

    __tablename__ = "rl_q_table"

    user_id: int = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    state: str = Column(Text, primary_key=True)
    action: str = Column(Text, primary_key=True)
    q_value: float = Column(Float, default=0.1)
    visit_count: int = Column(Integer, default=0)
    updated_at: datetime = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return (
            f"<RLQTable user={self.user_id} state={self.state!r} "
            f"action={self.action!r} q={self.q_value:.3f}>"
        )


class RLAttemptLog(Base):
    """Full attempt log for audit, debugging, and future DQN upgrade."""

    __tablename__ = "rl_attempt_log"

    id: int = Column(Integer, primary_key=True, index=True)
    user_id: Optional[int] = Column(Integer, ForeignKey("users.id"), nullable=True)
    session_id: Optional[int] = Column(Integer, nullable=True)
    question_id: Optional[int] = Column(Integer, nullable=True)
    difficulty: Optional[str] = Column(Text, nullable=True)
    state_before: Optional[str] = Column(Text, nullable=True)
    action_taken: Optional[str] = Column(Text, nullable=True)
    reward: Optional[float] = Column(Float, nullable=True)
    state_after: Optional[str] = Column(Text, nullable=True)
    response_time: Optional[float] = Column(Float, nullable=True)
    is_correct: Optional[bool] = Column(Boolean, nullable=True)
    created_at: datetime = Column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<RLAttemptLog id={self.id} user={self.user_id} reward={self.reward}>"
