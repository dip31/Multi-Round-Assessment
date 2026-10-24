"""Shared department-scope checks for faculty access to student records.

Current policy assumption: a faculty member may read only students whose
persisted StudentProfile department matches their authenticated
FacultyProfile department. TPO/admin policy is handled by each endpoint.
"""

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.profile import FacultyProfile, StudentProfile
from app.models.user import User


def get_faculty_department(db: Session, faculty: User) -> str:
    profile = faculty.faculty_profile or db.query(FacultyProfile).filter(
        FacultyProfile.user_id == faculty.id
    ).first()
    department = profile.department.strip() if profile and profile.department else ""
    if not department:
        raise HTTPException(
            status_code=403,
            detail="Faculty department scope is not configured.",
        )
    return department


def faculty_can_access_student(db: Session, faculty: User, student_id: int) -> bool:
    department = get_faculty_department(db, faculty)
    return db.query(StudentProfile.user_id).filter(
        StudentProfile.user_id == student_id,
        func.lower(StudentProfile.department) == department.lower(),
    ).first() is not None


def require_faculty_student_access(db: Session, faculty: User, student_id: int) -> None:
    if not faculty_can_access_student(db, faculty, student_id):
        # Avoid confirming that an out-of-scope student record exists.
        raise HTTPException(status_code=404, detail="Student record not found")
