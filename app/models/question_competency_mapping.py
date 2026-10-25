"""
SQLAlchemy ORM models for question-to-competency mappings.

Maps questions (aptitude and coding) to canonical competencies
for competency-based assessment and portfolio verification.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.aptitude import AptitudeQuestion
    from app.models.coding import CodingProblem


class QuestionCompetencyMapping(Base):
    """Maps a question to one or more canonical competencies.
    
    Source types:
    - 'aptitude': AptitudeQuestion
    - 'coding': CodingProblem
    """
    
    __tablename__ = "question_competency_mappings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Source question identification
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    
    # Canonical competency reference
    competency_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    skill_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    # Weight/relevance of this question for the competency (0.0-1.0)
    weight: Mapped[float] = mapped_column(default=1.0, nullable=False)
    
    # Metadata
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", "competency_code", name="uq_question_competency"),
    )
    
    def __repr__(self) -> str:
        return f"<QuestionCompetencyMapping {self.source_type}:{self.source_id} -> {self.competency_code}>"


# Source type constants
SOURCE_TYPE_APTITUDE = "aptitude"
SOURCE_TYPE_CODING = "coding"
VALID_SOURCE_TYPES = {SOURCE_TYPE_APTITUDE, SOURCE_TYPE_CODING}