"""
ORM Models — Coding Round

Maps to PostgreSQL tables: coding_problems, coding_test_cases,
coding_submissions, session_problems.

Schema changes must go through Alembic migrations — never edit columns here
directly without a corresponding migration.
"""

from datetime import datetime
from sqlalchemy import (Column, Integer, String, Text, Float, Boolean,
                        DateTime, ForeignKey, ARRAY, UniqueConstraint)
from sqlalchemy.orm import relationship

from app.database.base import Base


class CodingProblem(Base):
    __tablename__ = "coding_problems"

    id            = Column(Integer, primary_key=True, index=True)
    title         = Column(String(200), nullable=False)
    description   = Column(Text, nullable=False)
    difficulty    = Column(String(10), nullable=False)   # easy | medium | hard
    tags          = Column(ARRAY(String), default=[])
    input_format  = Column(Text)
    output_format = Column(Text)
    constraints   = Column(Text)
    created_by    = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at    = Column(DateTime, default=datetime.utcnow)

    test_cases          = relationship("CodingTestCase",
                                       back_populates="problem",
                                       cascade="all, delete-orphan")
    submissions         = relationship("CodingSubmission",
                                       back_populates="problem")
    session_assignments = relationship("SessionProblem",
                                       back_populates="problem")


class CodingTestCase(Base):
    __tablename__ = "coding_test_cases"

    id              = Column(Integer, primary_key=True, index=True)
    problem_id      = Column(Integer, ForeignKey("coding_problems.id"),
                             nullable=False)
    input_data      = Column(Text, nullable=False)
    expected_output = Column(Text, nullable=False)
    is_hidden       = Column(Boolean, default=True)
    case_order      = Column(Integer, default=0)
    explanation     = Column(Text)

    problem = relationship("CodingProblem", back_populates="test_cases")


class CodingSubmission(Base):
    __tablename__ = "coding_submissions"

    id             = Column(Integer, primary_key=True, index=True)
    round_id       = Column(Integer, ForeignKey("assessment_rounds.id"),
                            nullable=False)
    problem_id     = Column(Integer, ForeignKey("coding_problems.id"),
                            nullable=False)
    code           = Column(Text, nullable=False)
    language       = Column(String(50), nullable=False)
    judge0_token   = Column(String(100), nullable=True)
    status         = Column(String(30), default="running")
    # status values: running | accepted | wrong_answer |
    #                runtime_error | time_limit_exceeded | compilation_error
    score          = Column(Float, default=0.0)
    execution_time = Column(Float, nullable=True)
    memory_used    = Column(Integer, nullable=True)
    submitted_at   = Column(DateTime, default=datetime.utcnow)

    problem = relationship("CodingProblem", back_populates="submissions")


class SessionProblem(Base):
    """
    Assigns specific problems to a candidate's coding round.
    Created when candidate calls POST /coding/start-round.
    Enforces AMCAT-style problem isolation — candidates only see
    and can submit problems listed in their session_problems rows.
    """
    __tablename__ = "session_problems"

    id               = Column(Integer, primary_key=True, index=True)
    round_id         = Column(Integer, ForeignKey("assessment_rounds.id",
                                                   ondelete="CASCADE"), nullable=False)
    problem_id       = Column(Integer, ForeignKey("coding_problems.id"),
                               nullable=False)
    problem_order    = Column(Integer, default=0)
    marked_for_review = Column(Boolean, default=False)
    assigned_at      = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('round_id', 'problem_id', name='uq_session_problem'),
    )

    problem = relationship("CodingProblem", back_populates="session_assignments")
