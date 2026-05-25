"""
Candidate Form Input Agent — Stage 2
Form-based candidate information entry to replace scraping.
"""
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.database import get_db, generate_id
from shared.db.models import Candidate, Application, AuditLog
from shared.queue.event_bus import event_bus
from shared.queue.event_topics import EventTopics
from shared.auth.jwt_middleware import get_current_user

router = APIRouter(prefix="/sourcing", tags=["Candidate Intake — Stage 2"])


class CandidateFormInput(BaseModel):
    """Form input for candidate information (fields required by Stage 3 screening)."""
    name: str = Field(..., description="Candidate full name")
    email: Optional[str] = Field(None, description="Candidate email address")
    phone: Optional[str] = Field(None, description="Candidate phone number")
    location: Optional[str] = Field(None, description="Candidate location")
    current_role: Optional[str] = Field(None, description="Current job title/role")
    experience_years: float = Field(0, ge=0, description="Years of experience")
    skills: List[str] = Field(default_factory=list, description="List of skills")
    education: Optional[str] = Field(
        None,
        description="Highest education level (e.g. bachelor's, master's, phd)",
    )
    work_history: Optional[List[dict]] = Field(None, description="Work history (array of objects)")
    source_profile_url: Optional[str] = Field(None, description="LinkedIn/Portfolio URL")
    job_id: str = Field(..., description="Job ID to link candidate for screening")


class CandidateFormWithResume(CandidateFormInput):
    """Form input with optional resume file upload."""
    resume_file: Optional[str] = Field(None, description="Resume file path if uploaded separately")


@router.post("/add-candidate")
async def add_candidate_form(
    form_data: CandidateFormInput,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Add a candidate manually via form input.
    
    This replaces the scraping mechanism with direct form entry.
    All fields needed for subsequent stages (screening, outreach, etc.) are included.
    """
    from shared.db.models import Job
    result = await db.execute(select(Job).where(Job.id == form_data.job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job with id {form_data.job_id} not found")

    # Create candidate record with screening-ready fields
    candidate = Candidate(
        id=generate_id(),
        name=form_data.name,
        email=form_data.email,
        phone=form_data.phone,
        location=form_data.location,
        current_role=form_data.current_role,
        experience_years=form_data.experience_years,
        skills=json.dumps(form_data.skills) if form_data.skills else None,
        education=form_data.education,
        work_history=json.dumps(form_data.work_history) if form_data.work_history else None,
        source="manual_entry",
        source_profile_url=form_data.source_profile_url,
        status="parsed",
        job_id=form_data.job_id,
    )
    db.add(candidate)
    await db.flush()

    application = Application(
        id=generate_id(),
        job_id=form_data.job_id,
        candidate_id=candidate.id,
        status="sourced",
    )
    db.add(application)
    application_id = application.id
    
    # Audit log
    audit = AuditLog(
        id=generate_id(),
        event_type="candidate.manual_entry",
        agent_name="candidate_form_agent",
        entity_type="candidate",
        entity_id=candidate.id,
        details=json.dumps({
            "name": form_data.name,
            "email": form_data.email,
            "job_id": form_data.job_id,
            "application_id": application_id,
            "skills_count": len(form_data.skills) if form_data.skills else 0,
        }),
    )
    db.add(audit)
    await db.commit()
    
    await event_bus.publish(
        EventTopics.PROFILE_PARSED,
        {
            "candidate_id": candidate.id,
            "job_id": form_data.job_id,
            "application_id": application_id,
            "name": form_data.name,
            "source": "manual_entry",
        },
        agent="candidate_form_agent",
    )

    return {
        "success": True,
        "candidate_id": candidate.id,
        "name": form_data.name,
        "email": form_data.email,
        "job_id": form_data.job_id,
        "application_id": application_id,
        "status": "parsed",
        "message": "Candidate added successfully. Queued for screening.",
    }


@router.post("/add-candidate-with-resume")
async def add_candidate_with_resume(
    form_data: CandidateFormInput,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Add a candidate via form and link to an existing resume upload.
    
    Use this after uploading a resume via /sourcing/upload-resume to add
    additional information that wasn't parsed from the resume.
    """
    from shared.db.models import Job
    result = await db.execute(select(Job).where(Job.id == form_data.job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job with id {form_data.job_id} not found")

    # Create candidate record with screening-ready fields
    candidate = Candidate(
        id=generate_id(),
        name=form_data.name,
        email=form_data.email,
        phone=form_data.phone,
        location=form_data.location,
        current_role=form_data.current_role,
        experience_years=form_data.experience_years,
        skills=json.dumps(form_data.skills) if form_data.skills else None,
        education=form_data.education,
        work_history=json.dumps(form_data.work_history) if form_data.work_history else None,
        source="manual_entry",
        source_profile_url=form_data.source_profile_url,
        status="parsed",
        job_id=form_data.job_id,
    )
    db.add(candidate)
    await db.flush()

    application = Application(
        id=generate_id(),
        job_id=form_data.job_id,
        candidate_id=candidate.id,
        status="sourced",
    )
    db.add(application)
    application_id = application.id
    
    # Audit log
    audit = AuditLog(
        id=generate_id(),
        event_type="candidate.manual_entry",
        agent_name="candidate_form_agent",
        entity_type="candidate",
        entity_id=candidate.id,
        details=json.dumps({
            "name": form_data.name,
            "email": form_data.email,
            "job_id": form_data.job_id,
            "application_id": application_id,
            "skills_count": len(form_data.skills) if form_data.skills else 0,
        }),
    )
    db.add(audit)
    await db.commit()
    
    await event_bus.publish(
        EventTopics.PROFILE_PARSED,
        {
            "candidate_id": candidate.id,
            "job_id": form_data.job_id,
            "application_id": application_id,
            "name": form_data.name,
            "source": "manual_entry",
        },
        agent="candidate_form_agent",
    )

    return {
        "success": True,
        "candidate_id": candidate.id,
        "name": form_data.name,
        "email": form_data.email,
        "job_id": form_data.job_id,
        "application_id": application_id,
        "status": "parsed",
        "message": "Candidate added successfully. Upload resume separately to complete profile.",
    }


@router.put("/candidates/{candidate_id}")
async def update_candidate_form(
    candidate_id: str,
    form_data: CandidateFormInput,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Update an existing candidate's information via form.
    """
    # Fetch candidate
    result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    from shared.db.models import Job
    result = await db.execute(select(Job).where(Job.id == form_data.job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job with id {form_data.job_id} not found")

    candidate.name = form_data.name
    candidate.email = form_data.email
    candidate.phone = form_data.phone
    candidate.location = form_data.location
    candidate.current_role = form_data.current_role
    candidate.experience_years = form_data.experience_years
    candidate.skills = json.dumps(form_data.skills) if form_data.skills else None
    candidate.education = form_data.education
    candidate.work_history = json.dumps(form_data.work_history) if form_data.work_history else None
    candidate.source_profile_url = form_data.source_profile_url

    if form_data.job_id != candidate.job_id:
        candidate.job_id = form_data.job_id
        # Create new application if job_id changed
        application = Application(
            id=generate_id(),
            job_id=form_data.job_id,
            candidate_id=candidate.id,
            status="sourced",
        )
        db.add(application)
    
    await db.commit()
    
    return {
        "success": True,
        "candidate_id": candidate.id,
        "name": candidate.name,
        "message": "Candidate updated successfully",
    }


@router.get("/form-fields")
async def get_form_fields():
    """
    Get the available form fields and their descriptions.
    Useful for dynamically generating forms in the frontend.
    """
    return {
        "fields": {
            "name": {
                "type": "string",
                "required": True,
                "description": "Candidate full name",
                "example": "John Doe"
            },
            "email": {
                "type": "string",
                "required": False,
                "description": "Candidate email address",
                "example": "john.doe@example.com"
            },
            "phone": {
                "type": "string",
                "required": False,
                "description": "Candidate phone number",
                "example": "+1 234 567 8900"
            },
            "location": {
                "type": "string",
                "required": False,
                "description": "Candidate location",
                "example": "San Francisco, CA"
            },
            "current_role": {
                "type": "string",
                "required": False,
                "description": "Current job title/role",
                "example": "Senior Software Engineer"
            },
            "experience_years": {
                "type": "float",
                "required": False,
                "description": "Years of experience",
                "example": 5.5,
                "minimum": 0
            },
            "skills": {
                "type": "array",
                "required": False,
                "description": "List of technical skills",
                "example": ["Python", "JavaScript", "React", "SQL"]
            },
            "education": {
                "type": "string",
                "required": False,
                "description": "Highest education level for screening",
                "example": "bachelor's",
                "options": ["high school", "associate", "bachelor's", "master's", "phd"],
            },
            "work_history": {
                "type": "array",
                "required": False,
                "description": "Work history (array of objects with company, role, years)",
                "example": [{"company": "Google", "role": "Software Engineer", "years": "2020-2023"}]
            },
            "source_profile_url": {
                "type": "string",
                "required": False,
                "description": "LinkedIn/Portfolio URL",
                "example": "https://linkedin.com/in/johndoe"
            },
            "job_id": {
                "type": "string",
                "required": True,
                "description": "Job ID to link candidate for screening",
                "example": "job_12345"
            }
        }
    }
