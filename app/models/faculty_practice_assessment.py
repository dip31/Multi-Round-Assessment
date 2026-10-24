"""Persisted faculty-authored practice assessments and student progress links."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class FacultyPracticeAssessment(Base):
    __tablename__ = "faculty_practice_assessments"
    __table_args__ = (UniqueConstraint("faculty_id", "request_key", name="uq_faculty_practice_request_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    faculty_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    request_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    availability_start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    availability_end: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="published")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class FacultyPracticeAssessmentRound(Base):
    __tablename__ = "faculty_practice_assessment_rounds"
    __table_args__ = (UniqueConstraint("assessment_id", "sequence", name="uq_faculty_practice_round_sequence"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("faculty_practice_assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    round_type: Mapped[str] = mapped_column(String(20), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    configuration: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")


class FacultyPracticeAssignment(Base):
    __tablename__ = "faculty_practice_assignments"
    __table_args__ = (UniqueConstraint("assessment_id", "student_id", name="uq_faculty_practice_recipient"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assessment_id: Mapped[int] = mapped_column(ForeignKey("faculty_practice_assessments.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())


class FacultyPracticeRoundAttempt(Base):
    __tablename__ = "faculty_practice_round_attempts"
    __table_args__ = (
        UniqueConstraint("assignment_id", "assessment_round_id", name="uq_faculty_practice_round_attempt"),
        UniqueConstraint("session_id", "round_id", name="uq_faculty_practice_engine_link"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assignment_id: Mapped[int] = mapped_column(ForeignKey("faculty_practice_assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    assessment_round_id: Mapped[int] = mapped_column(ForeignKey("faculty_practice_assessment_rounds.id", ondelete="CASCADE"), nullable=False)
    session_id: Mapped[int] = mapped_column(ForeignKey("assessment_sessions.id", ondelete="CASCADE"), nullable=False)
    round_id: Mapped[int] = mapped_column(ForeignKey("assessment_rounds.id", ondelete="CASCADE"), nullable=False)
