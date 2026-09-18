"""
Pydantic schemas for EDI5 Identity & Role Profiles.
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


# ── Student Profile Schemas ───────────────────────────────────────────

class StudentProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, max_length=150)
    roll_number: Optional[str] = None
    department: Optional[str] = Field(None, max_length=100)
    cgpa: Optional[float] = Field(None, ge=0.0, le=10.0)
    graduation_year: Optional[int] = Field(None, ge=2020, le=2035)
    backlogs_count: Optional[int] = Field(None, ge=0)
    institution: Optional[str] = Field(None, max_length=200)
    target_role: Optional[str] = Field(None, max_length=100)
    skills: Optional[List[str]] = None
    phone_number: Optional[str] = None
    mobile_no: Optional[str] = None
    college_email_id: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    tenth_marks: Optional[float] = Field(None, ge=0.0, le=100.0)
    twelfth_marks: Optional[float] = Field(None, ge=0.0, le=100.0)
    bio: Optional[str] = None


class PlacementEligibility(BaseModel):
    status: str
    label: str
    badge_variant: str
    message: str
    is_eligible: bool


class StudentProfileResponse(BaseModel):
    id: int
    user_id: int
    full_name: Optional[str] = None
    roll_number: Optional[str] = None
    department: str
    cgpa: float
    graduation_year: int
    backlogs_count: int
    institution: str
    target_role: Optional[str] = None
    skills: List[str] = []
    phone_number: Optional[str] = None
    mobile_no: Optional[str] = None
    college_email_id: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[str] = None
    nationality: Optional[str] = "Indian"
    tenth_marks: Optional[float] = None
    twelfth_marks: Optional[float] = None
    bio: Optional[str] = None
    placement_eligibility: Optional[PlacementEligibility] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Faculty Profile Schemas ───────────────────────────────────────────

class FacultyProfileUpdate(BaseModel):
    department: Optional[str] = Field(None, max_length=100)
    designation: Optional[str] = Field(None, max_length=100)
    institution: Optional[str] = Field(None, max_length=200)
    employee_id: Optional[str] = None
    bio: Optional[str] = None


class FacultyProfileResponse(BaseModel):
    id: int
    user_id: int
    department: str
    designation: str
    institution: str
    employee_id: Optional[str] = None
    bio: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── TPO Profile Schemas ───────────────────────────────────────────────

class TPOProfileUpdate(BaseModel):
    institution: Optional[str] = Field(None, max_length=200)
    designation: Optional[str] = Field(None, max_length=100)
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    bio: Optional[str] = None


class TPOProfileResponse(BaseModel):
    id: int
    user_id: int
    institution: str
    designation: str
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    bio: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── User Resume Schemas ───────────────────────────────────────────────

class UserResumeResponse(BaseModel):
    id: int
    user_id: int
    cv_name: str
    cv_type: str
    file_name: str
    file_size: int
    parsed_skills: list = []
    parsed_projects: list = []
    uploaded_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Unified User Profile Response ─────────────────────────────────────

class UserProfileResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str
    is_active: bool
    is_verified: bool
    created_at: Optional[datetime] = None
    student_profile: Optional[StudentProfileResponse] = None
    faculty_profile: Optional[FacultyProfileResponse] = None
    tpo_profile: Optional[TPOProfileResponse] = None
    resumes: Optional[list[UserResumeResponse]] = None

    model_config = {"from_attributes": True}
