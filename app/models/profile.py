"""
SQLAlchemy ORM models for EDI5 Identity & Role Profiles:
- StudentProfile
- FacultyProfile
- TPOProfile
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class StudentProfile(Base):
    """Academic and placement-readiness profile for students."""

    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    roll_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    department: Mapped[str] = mapped_column(String(100), default="Computer Science", nullable=False)
    cgpa: Mapped[float] = mapped_column(Float, default=7.50, nullable=False)
    graduation_year: Mapped[int] = mapped_column(Integer, default=2026, nullable=False)
    backlogs_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    institution: Mapped[str] = mapped_column(String(200), default="Engineering College", nullable=False)
    target_role: Mapped[Optional[str]] = mapped_column(
        String(100), default="Software Development Engineer", nullable=True
    )
    skills_json: Mapped[dict | list] = mapped_column(JSONB, default=list, nullable=False)
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    mobile_no: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    college_email_id: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    date_of_birth: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    nationality: Mapped[Optional[str]] = mapped_column(String(100), default="Indian", nullable=True)
    tenth_marks: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    twelfth_marks: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    portfolio_data: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="student_profile")


class FacultyProfile(Base):
    """Departmental profile for faculty members."""

    __tablename__ = "faculty_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    department: Mapped[str] = mapped_column(String(100), default="Computer Science", nullable=False)
    designation: Mapped[str] = mapped_column(String(100), default="Assistant Professor", nullable=False)
    institution: Mapped[str] = mapped_column(String(200), default="Engineering College", nullable=False)
    employee_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="faculty_profile")


class TPOProfile(Base):
    """Placement cell profile for TPO officers."""

    __tablename__ = "tpo_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    institution: Mapped[str] = mapped_column(String(200), default="Engineering College", nullable=False)
    designation: Mapped[str] = mapped_column(
        String(100), default="Training & Placement Officer", nullable=False
    )
    contact_email: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="tpo_profile")


class UserResume(Base):
    """Uploaded resumes/CVs associated with a student/user."""

    __tablename__ = "user_resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cv_name: Mapped[str] = mapped_column(String(200), default="My Resume", nullable=False)
    cv_type: Mapped[str] = mapped_column(String(100), default="Software Developer", nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), default="resume.pdf", nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    resume_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parsed_skills: Mapped[dict | list] = mapped_column(JSONB, default=list, nullable=False)
    parsed_projects: Mapped[dict | list] = mapped_column(JSONB, default=list, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="resumes")
