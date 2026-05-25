"""
SQLAlchemy ORM model for proctoring events table.

Tracks candidate behavior during assessment sessions for integrity monitoring.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.database.base import Base


class ProctoringEvent(Base):
    """Represents a proctoring event during an assessment session.

    Records suspicious behavior or policy violations for later admin review.
    """

    __tablename__ = "proctoring_events"

    id: int = Column(Integer, primary_key=True, index=True)
    session_id: int = Column(
        Integer,
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: str = Column(String(50), nullable=False, index=True)
    event_metadata: Optional[dict] = Column(JSONB, nullable=True)
    created_at: datetime = Column(DateTime, server_default=text("NOW()"))

    # ── Relationships ─────────────────────────────────────────────────
    session = relationship(
        "AssessmentSession",
        back_populates="proctoring_events",
    )

    def __repr__(self) -> str:
        return (
            f"<ProctoringEvent id={self.id} session_id={self.session_id} "
            f"event_type={self.event_type!r}>"
        )
