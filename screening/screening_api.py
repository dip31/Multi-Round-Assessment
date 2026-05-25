"""
Screening API — Stage 3 endpoints for candidate screening and shortlisting.
"""
import json
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from shared.db.database import get_db
from shared.db.models import Application, Candidate, Job
from shared.queue.event_bus import event_bus
from shared.queue.event_topics import EventTopics
from screening.scoring_engine import calculate_score
from screening.candidate_job_linker import link_candidates_to_jobs

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/screening", tags=["screening"])


class ScreeningRequest(BaseModel):
    candidate_ids: Optional[List[str]] = None
    job_id: Optional[str] = None
    force_rescreen: bool = False


class ScreeningStats(BaseModel):
    total_candidates: int
    screened: int
    shortlisted: int
    rejected: int
    duplicates: int
    avg_score: float


async def process_candidate_async(candidate_id: str, db: AsyncSession):
    """Async version of process_candidate for API use."""
    from screening.duplicate_detector import check_duplicate_async
    
    SHORTLIST_THRESHOLD = 70
    
    # Fetch candidate
    result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        logger.error("Candidate not found: %s", candidate_id)
        return None

    # Fetch application if exists
    app_result = await db.execute(
        select(Application).where(
            Application.candidate_id == candidate.id,
            Application.job_id == candidate.job_id,
        )
    )
    application = app_result.scalar_one_or_none()

    async def set_application_status(status: str):
        if not candidate.job_id:
            return
        app_result = await db.execute(
            select(Application).where(
                Application.candidate_id == candidate.id,
                Application.job_id == candidate.job_id,
            )
        )
        application = app_result.scalar_one_or_none()
        if application:
            application.status = "SHORTLISTED" if status == "shortlisted" else "REJECTED"
    
    # Fetch job if linked
    if not candidate.job_id:
        app_result = await db.execute(
            select(Application).where(Application.candidate_id == candidate.id).limit(1)
        )
        application = app_result.scalar_one_or_none()
        if application and application.job_id:
            candidate.job_id = application.job_id
            logger.info("Linked candidate %s to job %s through Application", candidate_id, candidate.job_id)
        else:
            logger.error("Candidate %s has no job_id", candidate_id)
            candidate.status = "rejected"
            candidate.rejection_reason = "No job_id assigned"
            await db.commit()
            return {"candidate_id": candidate_id, "job_id": None, "application_id": None, "status": "rejected", "score": 0, "is_duplicate": False}
    
    result = await db.execute(select(Job).where(Job.id == candidate.job_id))
    job = result.scalar_one_or_none()
    if not job:
        logger.error("Job not found: %s (candidate %s)", candidate.job_id, candidate_id)
        candidate.status = "rejected"
        candidate.rejection_reason = f"Job {candidate.job_id} not found"
        await set_application_status("rejected")
        await db.commit()
        return {"candidate_id": candidate_id, "job_id": candidate.job_id, "application_id": application.id if application else None, "status": "rejected", "score": 0, "is_duplicate": False}
    
    # Duplicate detection
    try:
        is_dup, original_id = await check_duplicate_async(candidate, db)
        if is_dup:
            candidate.is_duplicate = True
            candidate.merged_into = original_id
            candidate.status = "rejected"
            candidate.rejection_reason = f"Duplicate of candidate {original_id}"
            await set_application_status("rejected")
            await db.commit()
            logger.info("Candidate %s marked as duplicate of %s", candidate_id, original_id)
            return {
                "candidate_id": candidate_id,
                "job_id": candidate.job_id,
                "application_id": application.id if application else None,
                "status": "rejected",
                "score": 0,
                "is_duplicate": True,
            }
    except Exception as e:
        logger.exception("Duplicate detection failed for %s: %s", candidate_id, e)
    
    # Score candidate
    try:
        total_score, breakdown = calculate_score(candidate, job)
    except Exception as e:
        logger.exception("Scoring failed for %s: %s", candidate_id, e)
        candidate.status = "rejected"
        candidate.rejection_reason = f"Scoring error: {str(e)}"
        await set_application_status("rejected")
        await db.commit()
        return {"candidate_id": candidate_id, "job_id": candidate.job_id, "application_id": application.id if application else None, "status": "rejected", "score": 0, "is_duplicate": False}
    
    # Decide status
    if total_score >= SHORTLIST_THRESHOLD:
        status = "shortlisted"
        rejection_reason = None
    else:
        status = "rejected"
        rejection_reason = f"Score {total_score} below threshold {SHORTLIST_THRESHOLD}"
    
    # Update candidate
    candidate.score = total_score
    candidate.score_breakdown = json.dumps(breakdown)
    candidate.status = status
    candidate.rejection_reason = rejection_reason
    await set_application_status(status)
    
    await db.commit()
    
    logger.info("Candidate %s processed: status=%s score=%d", candidate_id, status, total_score)
    
    return {
        "candidate_id": candidate_id,
        "job_id": candidate.job_id,
        "application_id": application.id if application else None,
        "status": status,
        "score": total_score,
        "is_duplicate": False,
    }


@router.get("/stats", response_model=ScreeningStats)
async def get_screening_stats(job_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """Get screening statistics, optionally filtered by job."""
    
    query = select(Candidate)
    if job_id:
        query = query.where(Candidate.job_id == job_id)
    
    result = await db.execute(query)
    candidates = result.scalars().all()
    
    total = len(candidates)
    screened = len([c for c in candidates if c.score is not None])
    shortlisted = len([c for c in candidates if c.status == "shortlisted"])
    rejected = len([c for c in candidates if c.status == "rejected"])
    duplicates = len([c for c in candidates if c.is_duplicate])
    
    scores = [c.score for c in candidates if c.score is not None]
    avg_score = sum(scores) / len(scores) if scores else 0
    
    return ScreeningStats(
        total_candidates=total,
        screened=screened,
        shortlisted=shortlisted,
        rejected=rejected,
        duplicates=duplicates,
        avg_score=round(avg_score, 1)
    )


@router.get("/candidates")
async def get_screening_candidates(
    job_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Get candidates with screening results."""
    query = select(Candidate)
    
    if job_id:
        query = query.where(Candidate.job_id == job_id)
    if status:
        query = query.where(Candidate.status == status)
    
    query = query.limit(limit)
    result = await db.execute(query)
    candidates = result.scalars().all()
    
    result_list = []
    for c in candidates:
        candidate_data = {
            "id": c.id,
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "location": c.location,
            "current_role": c.current_role,
            "experience_years": c.experience_years,
            "skills": json.loads(c.skills) if c.skills else [],
            "education": c.education,
            "status": c.status,
            "source": c.source,
            "job_id": c.job_id,
            "score": c.score,
            "score_breakdown": json.loads(c.score_breakdown) if c.score_breakdown else None,
            "is_duplicate": c.is_duplicate,
            "merged_into": c.merged_into,
            "rejection_reason": c.rejection_reason,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        }
        result_list.append(candidate_data)
    
    return result_list


@router.post("/run")
async def run_screening(request: ScreeningRequest, db: AsyncSession = Depends(get_db)):
    """Run screening on specified candidates or all unscreened candidates."""
    
    # Determine which candidates to screen
    query = select(Candidate)
    
    if request.candidate_ids:
        query = query.where(Candidate.id.in_(request.candidate_ids))
    elif request.job_id:
        query = query.where(Candidate.job_id == request.job_id)
        if not request.force_rescreen:
            query = query.where(Candidate.score.is_(None))
    else:
        # Screen all unscreened candidates
        if not request.force_rescreen:
            query = query.where(Candidate.score.is_(None))
    
    result = await db.execute(query)
    candidates = result.scalars().all()
    
    if not candidates:
        return {
            "message": "No candidates found to screen",
            "screened_count": 0,
            "results": []
        }
    
    results = []
    screened_count = 0
    
    for candidate in candidates:
        try:
            result = await process_candidate_async(candidate.id, db)
            if result:
                results.append(result)
                screened_count += 1
                
                # Publish screening event
                await event_bus.publish("candidate.screened", {
                    "candidate_id": candidate.id,
                    "job_id": result.get("job_id") or candidate.job_id,
                    "application_id": result.get("application_id"),
                    "status": result["status"],
                    "score": result["score"],
                    "is_duplicate": result["is_duplicate"]
                })

                next_topic = (
                    EventTopics.CANDIDATE_SHORTLISTED
                    if result["status"] == "shortlisted"
                    else EventTopics.CANDIDATE_REJECTED
                )
                await event_bus.publish(next_topic, {
                    "candidate_id": candidate.id,
                    "job_id": result.get("job_id") or candidate.job_id,
                    "application_id": result.get("application_id"),
                    "status": result["status"],
                    "score": result["score"],
                    "is_duplicate": result["is_duplicate"]
                }, agent="screening_api")
                
        except Exception as e:
            logger.exception(f"Failed to screen candidate {candidate.id}: {e}")
            results.append({
                "candidate_id": candidate.id,
                "status": "error",
                "error": str(e)
            })
    
    return {
        "message": f"Screened {screened_count} candidates",
        "screened_count": screened_count,
        "results": results
    }


@router.post("/score/{candidate_id}")
async def score_candidate(candidate_id: str, job_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """Calculate score for a specific candidate against a job."""
    
    result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Use provided job_id or candidate's linked job
    target_job_id = job_id or candidate.job_id
    if not target_job_id:
        raise HTTPException(status_code=400, detail="No job specified for scoring")
    
    result = await db.execute(select(Job).where(Job.id == target_job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    try:
        total_score, breakdown = calculate_score(candidate, job)
        return {
            "candidate_id": candidate_id,
            "job_id": target_job_id,
            "total_score": total_score,
            "breakdown": breakdown
        }
    except Exception as e:
        logger.exception(f"Failed to score candidate {candidate_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Scoring failed: {str(e)}")


@router.get("/jobs")
async def get_jobs_with_candidates(db: AsyncSession = Depends(get_db)):
    """Get jobs with candidate counts for screening dashboard."""
    result = await db.execute(select(Job))
    jobs = result.scalars().all()
    
    result_list = []
    for job in jobs:
        # Get candidates for this job
        candidates_result = await db.execute(select(Candidate).where(Candidate.job_id == job.id))
        candidates = candidates_result.scalars().all()
        
        screened = len([c for c in candidates if c.score is not None])
        shortlisted = len([c for c in candidates if c.status == "shortlisted"])
        
        job_data = {
            "id": job.id,
            "title": job.title,
            "department": job.department,
            "location": job.location,
            "status": job.status,
            "skills": json.loads(job.skills) if job.skills else [],
            "experience_min": job.experience_min,
            "experience_max": job.experience_max,
            "qualification": job.qualification,
            "candidate_count": len(candidates),
            "screened_count": screened,
            "shortlisted_count": shortlisted,
            "created_at": job.created_at.isoformat() if job.created_at else None
        }
        result_list.append(job_data)
    
    return result_list


@router.delete("/reset/{candidate_id}")
async def reset_screening(candidate_id: str, db: AsyncSession = Depends(get_db)):
    """Reset screening results for a candidate."""
    
    result = await db.execute(select(Candidate).where(Candidate.id == candidate_id))
    candidate = result.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    # Reset screening fields
    candidate.score = None
    candidate.score_breakdown = None
    candidate.is_duplicate = False
    candidate.merged_into = None
    candidate.rejection_reason = None
    candidate.status = "new"
    
    await db.commit()
    
    return {
        "message": f"Screening results reset for candidate {candidate.name}",
        "candidate_id": candidate_id
    }


@router.post("/link-candidates")
async def link_candidates_to_jobs_endpoint(db: AsyncSession = Depends(get_db)):
    """Link candidates to jobs through Application records for candidates missing job_id."""
    
    # Use sync session for the linking utility
    from shared.db.database import db_session
    
    with db_session() as sync_db:
        result = link_candidates_to_jobs(sync_db)
    
    return {
        "message": f"Candidate linking completed",
        "linked_candidates": result["linked"],
        "unlinked_candidates": result["unlinked"],
        "total_processed": result["total_processed"]
    }


# ── End of screening API endpoints ──
