"""
Prescreening API — Stage 5 REST endpoints
Provides API access to prescreening chatbot and BGV functionality
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.database import get_db
from shared.db.models import Candidate, Job, Application

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/prescreening", tags=["prescreening"])


def _application_stage(status: Optional[str]) -> Optional[int]:
    if status in {"OUTREACH_SENT", "PRESCREENING"}:
        return 5
    if status in {"PRESCREENED", "SELECTED", "INTERVIEW", "INTERVIEW_SCHEDULED"}:
        return 6
    return None


class PrescreeningStats(BaseModel):
    total_in_prescreening: int
    sessions_created: int
    sessions_completed: int
    passed: int
    failed: int
    bgv_pending: int
    bgv_cleared: int


@router.get("/stats", response_model=PrescreeningStats)
async def get_prescreening_stats(job_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """Get prescreening statistics, optionally filtered by job."""
    
    query = select(Application)
    if job_id:
        query = query.where(Application.job_id == job_id)
    
    result = await db.execute(query)
    applications = result.scalars().all()
    
    in_prescreening = len([a for a in applications if a.status in ["OUTREACH_SENT", "PRESCREENING"]])
    prescreened = len([a for a in applications if a.status == "PRESCREENED"])
    
    return PrescreeningStats(
        total_in_prescreening=in_prescreening,
        sessions_created=in_prescreening,
        sessions_completed=prescreened,
        passed=prescreened,
        failed=0,
        bgv_pending=0,
        bgv_cleared=0
    )


@router.get("/candidates")
async def get_prescreening_candidates(
    job_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Get candidates in prescreening stage."""
    query = select(Candidate).join(Application)
    
    if job_id:
        query = query.where(Application.job_id == job_id)
    
    if status:
        query = query.where(Application.status == status)
    else:
        # Default to prescreening-related statuses
        query = query.where(Application.status.in_(["OUTREACH_SENT", "PRESCREENING", "PRESCREENED"]))
    
    query = query.limit(limit)
    result = await db.execute(query)
    candidates = result.scalars().all()
    
    result_list = []
    for c in candidates:
        # Get application info
        app_result = await db.execute(
            select(Application).where(
                Application.candidate_id == c.id,
                Application.job_id == job_id if job_id else True
            ).limit(1)
        )
        app = app_result.scalar_one_or_none()
        
        candidate_data = {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "location": c.location,
            "status": c.status,
            "application_status": app.status if app else None,
            "application_stage": _application_stage(app.status) if app else None,
            "score": c.score,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        result_list.append(candidate_data)
    
    return result_list


@router.get("/sessions")
async def get_prescreening_sessions(
    job_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Get prescreening chatbot sessions."""
    from shared.db.models import ChatbotSession, ChatbotAnswer
    
    query = select(ChatbotSession)
    
    if job_id:
        query = query.where(ChatbotSession.job_id == job_id)
    
    if status:
        query = query.where(ChatbotSession.status == status)
    
    query = query.limit(limit).order_by(ChatbotSession.created_at.desc())
    result = await db.execute(query)
    sessions = result.scalars().all()
    
    result_list = []
    for session in sessions:
        # Get candidate info
        candidate_result = await db.execute(
            select(Candidate).where(Candidate.id == session.candidate_id)
        )
        candidate = candidate_result.scalar_one_or_none()
        
        # Get job info
        job_result = await db.execute(
            select(Job).where(Job.id == session.job_id)
        )
        job = job_result.scalar_one_or_none()
        
        # Get answers count
        answers_result = await db.execute(
            select(ChatbotAnswer).where(ChatbotAnswer.session_id == session.session_id)
        )
        answers = answers_result.scalars().all()
        
        # Parse questions
        questions = []
        if session.questions:
            try:
                questions = json.loads(session.questions)
            except:
                questions = []
        
        session_data = {
            "session_id": session.session_id,
            "candidate_id": session.candidate_id,
            "candidate_name": candidate.name if candidate else "Unknown",
            "candidate_email": candidate.email if candidate else None,
            "job_id": session.job_id,
            "job_title": job.title if job else "Unknown",
            "status": session.status,
            "token": session.token,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "completed_at": session.completed_at.isoformat() if session.completed_at else None,
            "expires_at": session.expires_at.isoformat() if session.expires_at else None,
            "total_questions": len(questions),
            "answered_questions": len(answers),
            "questions": questions
        }
        result_list.append(session_data)
    
    return result_list


@router.get("/jobs")
async def get_jobs_with_prescreening(db: AsyncSession = Depends(get_db)):
    """Get jobs with prescreening statistics."""
    result = await db.execute(select(Job))
    jobs = result.scalars().all()
    
    result_list = []
    for job in jobs:
        # Get applications for this job
        apps_result = await db.execute(
            select(Application).where(Application.job_id == job.id)
        )
        applications = apps_result.scalars().all()
        
        in_prescreening = len([a for a in applications if a.status in ["OUTREACH_SENT", "PRESCREENING"]])
        prescreened = len([a for a in applications if a.status == "PRESCREENED"])
        
        job_data = {
            "id": job.id,
            "title": job.title,
            "department": job.department,
            "location": job.location,
            "status": job.status,
            "in_prescreening_count": in_prescreening,
            "prescreened_count": prescreened,
            "created_at": job.created_at.isoformat() if job.created_at else None
        }
        result_list.append(job_data)
    
    return result_list
