"""Admin feedback persistence for aptitude question review."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.database.base import Base


class AdminQuestionFeedback(Base):
    """Stores admin decisions and suggestions for aptitude questions."""

    __tablename__ = "admin_question_feedback"

    id: int = Column(Integer, primary_key=True, index=True)
    question_id: int = Column(
        Integer,
        ForeignKey("aptitude_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    admin_id: int = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: str = Column(String(20), nullable=False)  # approve | reject | flag
    suggestion: Optional[str] = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self) -> str:
        return (
            f"<AdminQuestionFeedback id={self.id} question_id={self.question_id} "
            f"action={self.action!r}>"
        )
