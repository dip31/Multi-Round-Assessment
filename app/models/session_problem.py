from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship

from app.database.base import Base


class SessionProblem(Base):
    """Assigned coding problems for a specific coding round.

    Mirrors the `session_problems` conceptual table described in the coding
    round design docs.
    """

    __tablename__ = "session_problems"

    id: int = Column(Integer, primary_key=True, index=True)
    round_id: int = Column(Integer, ForeignKey("assessment_rounds.id", ondelete="CASCADE"), nullable=False)
    problem_id: int = Column(Integer, ForeignKey("coding_problems.id", ondelete="CASCADE"), nullable=False)
    problem_order: int = Column(Integer, nullable=False, default=0)
    marked_for_review: bool = Column(Boolean, nullable=False, default=False)
    assigned_at: datetime = Column(DateTime, nullable=False)

    # Relationships
    problem = relationship("CodingProblem")

    def __repr__(self) -> str:
        return f"<SessionProblem id={self.id} round_id={self.round_id} problem_id={self.problem_id}>"
