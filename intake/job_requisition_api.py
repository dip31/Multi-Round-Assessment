"""
Job Requisition API Agent — Stage 1
REST API endpoint to create a job role with automatic JD generation.
Accepts role, skills, salary, headcount. Auto-generates professional JD. Stores in DB.
"""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.database import get_db, generate_id
from shared.db.models import Job, AuditLog
from shared.queue.event_bus import event_bus
from shared.queue.event_topics import EventTopics
from shared.auth.jwt_middleware import get_current_user
from config import GROQ_API_KEY

router = APIRouter(prefix="/intake", tags=["Intake — Stage 1"])


# ── JD Generation Functions ────────────────────────────

def _build_jd_prompt(job_data: dict) -> str:
    """Build the prompt for Groq to generate a professional JD."""
    skills_text = ', '.join(job_data.get('skills', [])) if job_data.get('skills') else 'Various technical skills'
    experience_text = f"{job_data.get('experience_min', 0)}-{job_data.get('experience_max', 5)} years" if job_data.get('experience_max', 0) > 0 else "Entry to mid-level"
    
    return f"""You are an expert HR recruiter. Generate a comprehensive, professional job description for the following role. Make it compelling and professional in tone.

Job Title: {job_data.get('title', 'N/A')}
Department: {job_data.get('department', 'Technology')}
Location: {job_data.get('location', 'Remote/Hybrid')}
Employment Type: {job_data.get('employment_type', 'full-time').replace('-', ' ').title()}
Experience Required: {experience_text}
Required Skills: {skills_text}

Generate the JD with these sections:
1. **About the Role** — 2-3 paragraph overview
2. **Key Responsibilities** — 6-8 bullet points
3. **Required Qualifications** — Technical and educational requirements
4. **Preferred Qualifications** — Nice-to-have skills
5. **What We Offer** — Benefits and perks
6. **How to Apply** — Brief application instructions

Make it sound professional, inclusive, and compelling. Use markdown formatting."""


async def _generate_with_groq(prompt: str) -> str:
    """Call Groq API to generate the JD."""
    if not GROQ_API_KEY:
        return _generate_fallback_jd()

    try:
        from groq import AsyncGroq
        
        client = AsyncGroq(api_key=GROQ_API_KEY)
        
        response = await client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are an expert HR recruiter and job description writer. Create compelling, professional job descriptions."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        print(f"⚠️ Groq API error: {e}")
        return _generate_fallback_jd()


def _generate_fallback_jd() -> str:
    """Generate a professional fallback JD when API is unavailable."""
    return """## About the Role

We are seeking a talented and motivated professional to join our dynamic team. This role offers 
an exciting opportunity to work on cutting-edge projects, collaborate with cross-functional teams, 
and make a significant impact on our organization's growth.

As a key member of the team, you will be responsible for designing, developing, and maintaining 
high-quality solutions that drive business value and contribute to our mission.

## Key Responsibilities

- Design and implement scalable, maintainable solutions aligned with business objectives
- Collaborate with cross-functional teams to define, design, and ship new features
- Write clean, efficient, and well-documented code following best practices
- Participate in code reviews and provide constructive feedback to team members
- Troubleshoot, debug, and optimize existing systems for performance and reliability
- Stay up-to-date with emerging technologies and industry trends
- Contribute to technical documentation and knowledge sharing initiatives
- Mentor junior team members and contribute to overall team growth

## Required Qualifications

- Bachelor's degree in Computer Science, Engineering, or related field
- Proven experience in a similar role with strong technical fundamentals
- Excellent problem-solving and analytical skills
- Strong communication and collaboration abilities
- Experience with agile development methodologies
- Commitment to writing clean, maintainable code

## Preferred Qualifications

- Master's degree or higher in a relevant field
- Experience with cloud platforms (AWS, GCP, or Azure)
- Contributions to open-source projects
- Previous leadership or mentoring experience
- Industry certifications relevant to the role

## What We Offer

- Competitive salary and comprehensive benefits package
- Health, dental, and vision insurance coverage
- Flexible work arrangements and remote work options
- Professional development budget and learning opportunities
- Regular team building activities and company events
- Modern office space equipped with the latest technology
- Opportunity for career growth and advancement

## How to Apply

Submit your resume and a brief cover letter explaining why you're excited about this role and how your experience aligns with our requirements. We look forward to hearing from you!

---
*Professional job description generated by our AI recruitment system.*
"""


# ── Request / Response Schemas ─────────────────────────
class JobCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    department: str = ""
    location: str = ""
    employment_type: str = "full-time"
    experience_min: int = 0
    experience_max: int = 0
    salary_min: float = 0
    salary_max: float = 0
    currency: str = "INR"
    skills: list[str] = []
    headcount: int = 1


class JobResponse(BaseModel):
    id: str
    title: str
    department: str | None
    location: str | None
    employment_type: str
    experience_min: int
    experience_max: int
    salary_min: float | None
    salary_max: float | None
    currency: str
    skills: list[str]
    description: str | None
    status: str
    headcount: int
    created_at: str

    class Config:
        from_attributes = True


# ── Endpoints ──────────────────────────────────────────

@router.post("/jobs", response_model=dict)
async def create_job(
    req: JobCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Create a new job requisition with automatic professional JD generation."""
    job_id = generate_id()
    
    # Prepare job data for JD generation
    job_data = {
        "title": req.title,
        "department": req.department,
        "location": req.location,
        "employment_type": req.employment_type,
        "experience_min": req.experience_min,
        "experience_max": req.experience_max,
        "skills": req.skills,
    }
    
    # Generate professional job description
    prompt = _build_jd_prompt(job_data)
    description = await _generate_with_groq(prompt)
    
    # Create job with generated description
    job = Job(
        id=job_id,
        title=req.title,
        department=req.department,
        location=req.location,
        employment_type=req.employment_type,
        experience_min=req.experience_min,
        experience_max=req.experience_max,
        salary_min=req.salary_min,
        salary_max=req.salary_max,
        currency=req.currency,
        skills=json.dumps(req.skills),
        description=description,
        headcount=req.headcount,
        status="active",  # Set to active since JD is generated
    )
    db.add(job)

    # Audit log
    audit = AuditLog(
        id=generate_id(),
        event_type=EventTopics.JOB_CREATED,
        agent_name="job_requisition_agent",
        entity_type="job",
        entity_id=job_id,
        details=json.dumps({
            "title": req.title, 
            "user": user.get("sub"),
            "jd_generated": True,
            "api_used": bool(GROQ_API_KEY)
        }),
    )
    db.add(audit)
    await db.commit()

    # Publish event
    await event_bus.publish(
        EventTopics.JOB_CREATED,
        {
            "job_id": job_id, 
            "title": req.title, 
            "skills": req.skills,
            "jd_generated": True
        },
        agent="job_requisition_agent",
    )

    return {
        "success": True,
        "job_id": job_id,
        "title": req.title,
        "description": description,
        "message": f"Job '{req.title}' created with professional description",
        "api_used": bool(GROQ_API_KEY),
    }


@router.get("/jobs", response_model=list[dict])
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List all job requisitions."""
    result = await db.execute(select(Job).order_by(Job.created_at.desc()))
    jobs = result.scalars().all()
    return [
        {
            "id": j.id,
            "title": j.title,
            "department": j.department,
            "location": j.location,
            "employment_type": j.employment_type,
            "experience_min": j.experience_min,
            "experience_max": j.experience_max,
            "salary_min": j.salary_min,
            "salary_max": j.salary_max,
            "skills": json.loads(j.skills) if j.skills else [],
            "description": j.description,
            "status": j.status,
            "headcount": j.headcount,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs
    ]


@router.get("/jobs/{job_id}", response_model=dict)
async def get_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get a specific job by ID."""
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": job.id,
        "title": job.title,
        "department": job.department,
        "location": job.location,
        "employment_type": job.employment_type,
        "experience_min": job.experience_min,
        "experience_max": job.experience_max,
        "salary_min": job.salary_min,
        "salary_max": job.salary_max,
        "skills": json.loads(job.skills) if job.skills else [],
        "description": job.description,
        "status": job.status,
        "headcount": job.headcount,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }
