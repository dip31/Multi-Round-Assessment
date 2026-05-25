"""
Resume Collector Agent — Stage 2
API endpoint that accepts resume uploads (PDF/DOCX).
Stores in local storage (S3 in production). Queues for parsing.
"""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.database import get_db, generate_id
from shared.db.models import Candidate, Application, AuditLog
from shared.queue.event_bus import event_bus
from shared.queue.event_topics import EventTopics
from shared.storage.s3_client import storage_client
from shared.auth.jwt_middleware import get_current_user

router = APIRouter(prefix="/sourcing", tags=["Candidate Intake — Stage 2"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt"}


# ── Event Subscriber for Auto-Parsing ──────────────────────
async def auto_parse_uploaded_resume(payload: dict):
    """Automatically trigger resume parsing when a resume is uploaded."""
    try:
        from sourcing.profile_parser import _parse_uploaded_resume_internal
        await _parse_uploaded_resume_internal(payload["candidate_id"])
        print(f"✅ Auto-parsing triggered for candidate {payload['candidate_id']}")
    except Exception as e:
        print(f"❌ Auto-parsing failed for candidate {payload.get('candidate_id')}: {e}")


# Subscribe to resume upload events for automatic parsing
event_bus.subscribe(EventTopics.RESUME_UPLOADED, auto_parse_uploaded_resume)


@router.post("/upload-resume", response_model=dict)
async def upload_resume(
    file: UploadFile = File(...),
    job_id: str = None,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Upload a resume file (PDF/DOCX) for parsing."""
    # Validate file type
    filename = file.filename or "resume.pdf"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Read file contents
    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(file_bytes) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    # Save file to storage
    cand_id = generate_id()
    stored_filename = f"{cand_id}_{filename}"
    file_path = await storage_client.save_file(file_bytes, stored_filename, folder="resumes")

    # Create candidate record
    candidate = Candidate(
        id=cand_id,
        name=filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title(),
        resume_url=file_path,
        source="upload",
        status="uploaded",
        job_id=job_id,  # CRITICAL FIX: Set job_id directly on candidate
    )
    db.add(candidate)

    # Create application record if job_id provided
    application_id = None
    if job_id:
        application = Application(
            id=generate_id(),
            job_id=job_id,
            candidate_id=cand_id,
            status="applied",
        )
        db.add(application)
        application_id = application.id

    # Audit log
    audit = AuditLog(
        id=generate_id(),
        event_type=EventTopics.RESUME_UPLOADED,
        agent_name="resume_collector_agent",
        entity_type="candidate",
        entity_id=cand_id,
        details=json.dumps({
            "filename": filename, 
            "size_bytes": len(file_bytes),
            "job_id": job_id,
            "application_id": application_id
        }),
    )
    db.add(audit)
    await db.commit()

    # Publish event for parser to pick up
    await event_bus.publish(
        EventTopics.RESUME_UPLOADED,
        {
            "candidate_id": cand_id, 
            "file_path": file_path, 
            "filename": filename,
            "job_id": job_id,
            "application_id": application_id
        },
        agent="resume_collector_agent",
    )

    return {
        "success": True,
        "candidate_id": cand_id,
        "filename": filename,
        "file_path": file_path,
        "job_id": job_id,
        "application_id": application_id,
        "message": "Resume uploaded successfully. Queued for parsing.",
    }


@router.get("/candidates", response_model=list[dict])
async def list_candidates(
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """List all candidates in the system."""
    result = await db.execute(select(Candidate).order_by(Candidate.created_at.desc()))
    candidates = result.scalars().all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "location": c.location,
            "current_role": c.current_role,
            "experience_years": c.experience_years,
            "skills": json.loads(c.skills) if c.skills and c.skills.startswith('[') else [],
            "education": c.education if c.education else "",
            "source": c.source,
            "source_profile_url": c.source_profile_url,
            "status": c.status,
            "resume_url": c.resume_url,
            "parsed_data": json.loads(c.parsed_data) if c.parsed_data and c.parsed_data.startswith('{') else None,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in candidates
    ]


@router.get("/candidates/{candidate_id}", response_model=dict)
async def get_candidate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Get a specific candidate by ID."""
    result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {
        "id": candidate.id,
        "name": candidate.name,
        "email": candidate.email,
        "phone": candidate.phone,
        "location": candidate.location,
        "current_role": candidate.current_role,
        "experience_years": candidate.experience_years,
        "skills": json.loads(candidate.skills) if candidate.skills and candidate.skills.startswith('[') else [],
        "education": candidate.education if candidate.education else "",
        "work_history": json.loads(candidate.work_history) if candidate.work_history and candidate.work_history.startswith('[') else [],
        "source": candidate.source,
        "source_profile_url": candidate.source_profile_url,
        "status": candidate.status,
        "resume_url": candidate.resume_url,
        "raw_resume_text": candidate.raw_resume_text,
        "parsed_data": json.loads(candidate.parsed_data) if candidate.parsed_data else None,
        "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
    }
