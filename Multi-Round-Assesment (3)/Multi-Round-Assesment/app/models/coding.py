"""
SQLAlchemy ORM models for coding round tables.

Maps to the following PostgreSQL tables:
- coding_problems
- coding_test_cases
- coding_submissions
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database.base import Base


class CodingProblem(Base):
    """Represents a coding challenge problem.

    Columns mirror the ``coding_problems`` table in ``database/schema.sql``.
    """

    __tablename__ = "coding_problems"

    id: int = Column(Integer, primary_key=True, index=True)
    title: str = Column(String(200), nullable=False)
    description: str = Column(Text, nullable=False)
    difficulty: Optional[str] = Column(String(10), nullable=True)
    tags: Optional[List[str]] = Column(ARRAY(Text), nullable=True)
    input_format: Optional[str] = Column(Text, nullable=True)
    output_format: Optional[str] = Column(Text, nullable=True)
    constraints: Optional[str] = Column(Text, nullable=True)
    created_by: Optional[int] = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: datetime = Column(DateTime, server_default=func.now())

    # ── Relationships ─────────────────────────────────────────────────
    test_cases = relationship(
        "CodingTestCase",
        back_populates="problem",
        lazy="select",
        cascade="all, delete-orphan",
    )
    submissions = relationship(
        "CodingSubmission",
        back_populates="problem",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<CodingProblem id={self.id} title={self.title!r}>"


class CodingTestCase(Base):
    """Represents a test case for validating code submissions.

    Columns mirror the ``coding_test_cases`` table in ``database/schema.sql``.
    """

    __tablename__ = "coding_test_cases"

    id: int = Column(Integer, primary_key=True, index=True)
    problem_id: int = Column(
        Integer,
        ForeignKey("coding_problems.id", ondelete="CASCADE"),
        nullable=False,
    )
    input_data: str = Column(Text, nullable=False)
    expected_output: str = Column(Text, nullable=False)
    is_hidden: bool = Column(Boolean, nullable=False, server_default=text("true"))
    case_order: int = Column(Integer, nullable=False, server_default=text("0"))
    explanation: Optional[str] = Column(Text, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────
    problem = relationship("CodingProblem", back_populates="test_cases")

    def __repr__(self) -> str:
        return f"<CodingTestCase id={self.id} problem_id={self.problem_id}>"


class CodingSubmission(Base):
    """Records a code submission with Judge0 execution results.

    Columns mirror the ``coding_submissions`` table in ``database/schema.sql``.
    """

    __tablename__ = "coding_submissions"

    id: int = Column(Integer, primary_key=True, index=True)
    round_id: int = Column(
        Integer,
        ForeignKey("assessment_rounds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    problem_id: int = Column(Integer, ForeignKey("coding_problems.id"), nullable=False)
    code: str = Column(Text, nullable=False)
    language: Optional[str] = Column(String(50), nullable=True)
    judge0_token: Optional[str] = Column(String(100), nullable=True, index=True)
    status: Optional[str] = Column(String(30), nullable=True)
    score: Optional[float] = Column(Float, nullable=True)
    execution_time: Optional[float] = Column(Float, nullable=True)
    memory_used: Optional[int] = Column(Integer, nullable=True)
    submitted_at: datetime = Column(DateTime, server_default=func.now())

    # ── Relationships ─────────────────────────────────────────────────
    problem = relationship("CodingProblem", back_populates="submissions")

    def __repr__(self) -> str:
        return (
            f"<CodingSubmission id={self.id} problem_id={self.problem_id} "
            f"status={self.status!r}>"
        )
