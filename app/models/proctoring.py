"""
SQLAlchemy ORM model for proctoring events table.

Tracks candidate behavior during assessment sessions for integrity monitoring.
"""

from datetime import datetime
from typing import Optional
import json

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.orm import relationship

from app.database.base import Base


def json_serializer(value: Optional[dict]) -> Optional[str]:
    """Serialize dict to JSON string."""
    return json.dumps(value) if value is not None else None


def json_deserializer(value: Optional[str]) -> Optional[dict]:
    """Deserialize JSON string to dict."""
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None


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
    event_metadata: Optional[str] = Column(Text, nullable=True)
    created_at: datetime = Column(DateTime, server_default=text("NOW()"))

    # ── Relationships ─────────────────────────────────────────────────
    session = relationship(
        "AssessmentSession",
        back_populates="proctoring_events",
    )

    @property
    def metadata_dict(self) -> Optional[dict]:
        """Get event_metadata as a dict."""
        return json_deserializer(self.event_metadata)

    @metadata_dict.setter
    def metadata_dict(self, value: Optional[dict]) -> None:
        """Set event_metadata from a dict."""
        self.event_metadata = json_serializer(value)

    def __repr__(self) -> str:
        return (
            f"<ProctoringEvent id={self.id} session_id={self.session_id} "
            f"event_type={self.event_type!r}>"
        )
