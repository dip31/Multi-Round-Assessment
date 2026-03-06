"""
SQLAlchemy ORM model for the ``users`` table.
"""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database.base import Base


class User(Base):
    """Represents a registered platform user (student or admin).

    Columns mirror the ``users`` table defined in ``database/schema.sql``.
    """

    __tablename__ = "users"

    id: int = Column(Integer, primary_key=True, index=True)
    name: str = Column(String(100), nullable=False)
    email: str = Column(String(150), unique=True, nullable=False, index=True)
    password_hash: str = Column(String, nullable=False)
    role: str = Column(String(20), nullable=False, server_default=text("'student'"))
    is_active: bool = Column(Boolean, nullable=False, server_default=text("1"))
    is_verified: bool = Column(Boolean, nullable=False, server_default=text("0"))
    created_at: datetime = Column(DateTime, server_default=func.now())

    # ── Relationships ─────────────────────────────────────────────────
    assessment_sessions = relationship(
        "AssessmentSession",
        back_populates="user",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r}>"
