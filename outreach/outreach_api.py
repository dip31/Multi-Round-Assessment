"""
Outreach API — Stage 4 REST endpoints
Provides API access to outreach functionality and statistics
"""
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.database import get_db
from shared.db.models import Candidate, Job, Application, Communication, ChatbotSession
from shared.queue.event_bus import event_bus
from shared.queue.event_topics import EventTopics
from outreach.emailjs_sender import send_prescreening_invitation as send_invitation_email
from config import COMPANY_NAME, SCREENING_BASE_URL

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/outreach", tags=["outreach"])


def _application_stage(status: Optional[str]) -> Optional[int]:
    if status in {"SHORTLISTED"}:
        return 4
    if status in {"OUTREACH_SENT", "PRESCREENING", "PRESCREENED"}:
        return 5
    if status in {"SELECTED", "INTERVIEW", "INTERVIEW_SCHEDULED"}:
        return 6
    return None


class OutreachStats(BaseModel):
    total_shortlisted: int
    outreach_sent: int
    opened: int
    clicked: int
    replied: int
    unresponsive: int


class OutreachRequest(BaseModel):
    candidate_id: str
    job_id: str


@router.get("/stats", response_model=OutreachStats)
async def get_outreach_stats(job_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """Get outreach statistics, optionally filtered by job."""
    
    query = select(Application)
    if job_id:
        query = query.where(Application.job_id == job_id)
    
    result = await db.execute(query)
    applications = result.scalars().all()
    
    total_shortlisted = len([a for a in applications if a.status in ["SHORTLISTED", "OUTREACH_SENT", "PRESCREENING", "PRESCREENED"]])
    outreach_sent = len([a for a in applications if a.status in ["OUTREACH_SENT", "PRESCREENING", "PRESCREENED"]])
    unresponsive = len([a for a in applications if a.status == "UNRESPONSIVE"])
    
    return OutreachStats(
        total_shortlisted=total_shortlisted,
        outreach_sent=outreach_sent,
        opened=0,  # Would need communications table
        clicked=0,
        replied=0,
        unresponsive=unresponsive
    )


@router.get("/candidates")
async def get_outreach_candidates(
    job_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Get candidates in outreach stage."""
    query = select(Candidate, Application, Job).join(Application, Candidate.id == Application.candidate_id).join(Job, Application.job_id == Job.id)
    
    if job_id:
        query = query.where(Application.job_id == job_id)
    
    if status:
        query = query.where(Application.status == status)
    else:
        # Default to outreach-related statuses
        query = query.where(Application.status.in_(["SHORTLISTED", "OUTREACH_SENT", "PRESCREENING", "UNRESPONSIVE"]))
    
    query = query.limit(limit)
    result = await db.execute(query)
    rows = result.all()
    
    result_list = []
    for candidate, app, job in rows:
        candidate_data = {
            "id": candidate.id,
            "name": candidate.name,
            "email": candidate.email,
            "phone": candidate.phone,
            "location": candidate.location,
            "status": app.status if app else candidate.status,
            "application_status": app.status if app else None,
            "application_stage": _application_stage(app.status) if app else None,
            "job_id": app.job_id if app else None,
            "job_title": job.title if job else None,
            "score": candidate.score,
            "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
        }
        result_list.append(candidate_data)
    
    return result_list


@router.post("/send")
async def send_outreach(request: OutreachRequest, db: AsyncSession = Depends(get_db)):
    """Manually trigger outreach email for a candidate."""
    
    # Verify candidate and job exist
    result = await db.execute(select(Candidate).where(Candidate.id == request.candidate_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    result = await db.execute(select(Job).where(Job.id == request.job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Publish candidate.shortlisted event to trigger outreach
    await event_bus.publish(
        EventTopics.CANDIDATE_SHORTLISTED,
        {
            "candidate_id": request.candidate_id,
            "job_id": request.job_id,
            "name": candidate.name,
            "email": candidate.email,
        },
        agent="outreach_api_manual"
    )
    
    logger.info(f"Outreach triggered for candidate {request.candidate_id}")
    
    return {
        "message": "Outreach email queued",
        "candidate_id": request.candidate_id,
        "job_id": request.job_id
    }


@router.get("/jobs")
async def get_jobs_with_outreach(db: AsyncSession = Depends(get_db)):
    """Get jobs with outreach statistics."""
    result = await db.execute(select(Job))
    jobs = result.scalars().all()
    
    result_list = []
    for job in jobs:
        # Get applications for this job
        apps_result = await db.execute(
            select(Application).where(Application.job_id == job.id)
        )
        applications = apps_result.scalars().all()
        
        shortlisted = len([a for a in applications if a.status == "SHORTLISTED"])
        outreach_sent = len([a for a in applications if a.status in ["OUTREACH_SENT", "PRESCREENING"]])
        
        job_data = {
            "id": job.id,
            "title": job.title,
            "department": job.department,
            "location": job.location,
            "status": job.status,
            "shortlisted_count": shortlisted,
            "outreach_sent_count": outreach_sent,
            "created_at": job.created_at.isoformat() if job.created_at else None
        }
        result_list.append(job_data)
    
    return result_list


# ─────────────────────────────────────────────────────────────────────────────
# EMAIL WEBHOOK HANDLER - Disabled (using EmailJS)
# ─────────────────────────────────────────────────────────────────────────────
# Note: EmailJS doesn't provide webhook functionality like SendGrid
# For now, prescreening sessions are created manually or via API calls


async def auto_create_prescreening_session(candidate_id: str, job_id: str, db: AsyncSession):
    """
    Automatically create prescreening session for a candidate.
    This is the automation link between Stage 4 and Stage 5.
    """
    try:
        # Check if session already exists
        from shared.db.models import ChatbotSession
        result = await db.execute(
            select(ChatbotSession).where(
                ChatbotSession.candidate_id == candidate_id,
                ChatbotSession.job_id == job_id
            )
        )
        existing_session = result.scalar_one_or_none()
        
        if existing_session:
            logger.info(f"Prescreening session already exists for candidate {candidate_id}")
            return
        
        # Create new prescreening session
        import uuid
        from datetime import timedelta
        
        token = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=48)
        
        session = ChatbotSession(
            candidate_id=candidate_id,
            job_id=job_id,
            token=token,
            created_at=now,
            expires_at=expires_at,
            status="PENDING"
        )
        db.add(session)
        
        # Update application status
        result = await db.execute(
            select(Application).where(
                Application.candidate_id == candidate_id,
                Application.job_id == job_id
            )
        )
        app = result.scalar_one_or_none()
        if app:
            app.status = "PRESCREENING"

        await db.commit()
        
        # Send prescreening link via email
        screening_url = f"{SCREENING_BASE_URL}?token={token}"
        
        # Get candidate and job info
        candidate = await db.get(Candidate, candidate_id)
        job = await db.get(Job, job_id)
        
        if candidate and job:
            await send_prescreening_invitation(candidate, job, screening_url, db)
            logger.info(f"✅ Prescreening session created and invitation sent to {candidate.email}")
        
        # Publish event
        await event_bus.publish(
            "prescreening.session_created",
            {
                "candidate_id": candidate_id,
                "job_id": job_id,
                "session_id": str(session.session_id),
                "token": token,
                "screening_url": screening_url
            },
            agent="auto_prescreening"
        )
        
    except Exception as e:
        logger.exception(f"Error creating prescreening session: {e}")


async def send_prescreening_invitation(candidate: Candidate, job: Job, screening_url: str, db: AsyncSession):
    """Send prescreening chatbot invitation email via EmailJS."""
    try:
        first_name = candidate.name.split()[0] if candidate.name else "Candidate"
        
        # Use EmailJS to send invitation
        success = send_invitation_email(
            candidate_email=candidate.email,
            candidate_name=candidate.name,
            job_title=job.title,
            chatbot_url=screening_url
        )
        
        if success:
            # Log communication
            comm = Communication(
                candidate_id=candidate.id,
                job_id=job.id,
                communication_type="PRESCREENING_INVITATION",
                direction="OUTBOUND",
                subject=f"Next Step: Prescreening for {job.title} at {COMPANY_NAME}",
                content=f"Prescreening invitation sent with URL: {screening_url}",
                sent_at=datetime.now(timezone.utc)
            )
            db.add(comm)
            await db.commit()
            
            logger.info(f"Prescreening invitation sent to {candidate.email}")
        else:
            logger.error(f"Failed to send prescreening invitation to {candidate.email}")
        
    except Exception as e:
        logger.exception(f"Error sending prescreening invitation: {e}")
