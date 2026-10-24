"""Faculty-authored practice assessment assignment APIs."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.database.db import get_db
from app.models.faculty_practice_assessment import FacultyPracticeAssessment, FacultyPracticeAssignment
from app.models.profile import StudentProfile
from app.models.user import User
from app.services.faculty_access_service import get_faculty_department
from app.services.faculty_practice_assignment_service import (
    create_assessment,
    cancel_assessment,
    get_owned_assessment,
    get_student_assignment,
    serialize_assessment,
    serialize_assignment,
)

router = APIRouter(tags=["Faculty Practice Assessments"])


class RoundInput(BaseModel):
    round_type: str
    practice_type: str | None = None


class AssessmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    instructions: str | None = Field(default=None, max_length=5000)
    availability_start: datetime | None = None
    availability_end: datetime | None = None
    rounds: list[RoundInput] = Field(min_length=1, max_length=10)
    student_ids: list[int] = Field(min_length=1, max_length=500)


def _as_utc_naive(value: datetime | None):
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


@router.get("/faculty/practice-assessments/roster")
def get_authorized_roster(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "faculty":
        raise HTTPException(403, "Faculty access required.")
    department = get_faculty_department(db, user)
    rows = db.query(User, StudentProfile).join(
        StudentProfile, StudentProfile.user_id == User.id
    ).filter(
        User.role == "student",
        func.lower(StudentProfile.department) == department.lower(),
    ).order_by(User.name, User.id).all()
    return [{"id": student.id, "name": profile.full_name or student.name,
             "roll_number": profile.roll_number, "department": profile.department}
            for student, profile in rows]


@router.post("/faculty/practice-assessments", status_code=201)
def create_faculty_assessment(payload: AssessmentCreate, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=80), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    data = payload.model_dump()
    data["availability_start"] = _as_utc_naive(data["availability_start"])
    data["availability_end"] = _as_utc_naive(data["availability_end"])
    data["rounds"] = [item.model_dump() for item in payload.rounds]
    return create_assessment(db, user, data, request_key=idempotency_key)


@router.get("/faculty/practice-assessments")
def list_faculty_assessments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "faculty":
        raise HTTPException(403, "Faculty access required.")
    items = db.query(FacultyPracticeAssessment).filter_by(faculty_id=user.id).order_by(FacultyPracticeAssessment.created_at.desc()).all()
    return [serialize_assessment(db, item) for item in items]


@router.get("/faculty/practice-assessments/{assessment_id}")
def get_faculty_assessment(assessment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assessment = get_owned_assessment(db, user, assessment_id)
    return serialize_assessment(db, assessment, include_students=True)


@router.post("/faculty/practice-assessments/{assessment_id}/cancel")
def cancel_faculty_assessment(assessment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return cancel_assessment(db, user, assessment_id)


@router.get("/student/practice-assignments")
def list_student_assignments(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if user.role != "student":
        raise HTTPException(403, "Student access required.")
    assignments = db.query(FacultyPracticeAssignment).filter_by(student_id=user.id).order_by(FacultyPracticeAssignment.assigned_at.desc()).all()
    return [serialize_assignment(db, item) for item in assignments]


@router.get("/student/practice-assignments/{assignment_id}")
def get_student_assignment_detail(assignment_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    assignment = get_student_assignment(db, user, assignment_id)
    return serialize_assignment(db, assignment)
