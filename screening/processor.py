"""
Processor — core orchestration logic for screening a single candidate.

This is the ONLY module that touches business logic and the database.
shortlister.py calls this; scoring_engine and duplicate_detector are pure utilities.
"""
import json
import logging
from shared.db.models import Application, Candidate, Job
from screening.duplicate_detector import check_duplicate
from screening.scoring_engine import calculate_score
from screening.candidate_job_linker import ensure_candidate_job_link

logger = logging.getLogger(__name__)

SHORTLIST_THRESHOLD = 70


def _set_application_status(candidate_id, job_id, candidate_status, db_session):
    """Keep Application.status aligned with the screening decision."""
    if not job_id:
        return

    application = db_session.query(Application).filter(
        Application.candidate_id == candidate_id,
        Application.job_id == job_id,
    ).first()

    if not application:
        return

    application.status = "SHORTLISTED" if candidate_status == "shortlisted" else "REJECTED"


def process_candidate(candidate_id, db_session):
    """
    Screen a single candidate: duplicate detection → scoring → status update.

    Args:
        candidate_id: UUID string of the candidate to process.
        db_session: Active SQLAlchemy session (caller owns commit/rollback).

    Returns:
        dict with keys: candidate_id, status, score, is_duplicate
        or None if candidate/job not found.
    """
    # ── 1. Fetch candidate ────────────────────────────────────────────────────
    candidate = db_session.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        logger.error("Candidate not found: %s", candidate_id)
        return None

    logger.info("Processing candidate %s: name=%s, job_id=%s", 
                candidate_id, candidate.name, candidate.job_id)

    # ── 2. Fetch job ──────────────────────────────────────────────────────────
    if not candidate.job_id:
        # Try to link candidate to job through Application table
        if ensure_candidate_job_link(candidate_id, db_session):
            logger.info("Successfully linked candidate %s to job %s", candidate_id, candidate.job_id)
        else:
            logger.error("Candidate %s has no job_id and could not be linked to any job", candidate_id)
            candidate.status = "rejected"
            candidate.rejection_reason = "No job_id assigned - cannot screen without job requirements"
            _set_application_status(candidate_id, candidate.job_id, "rejected", db_session)
            db_session.commit()
            return {"candidate_id": candidate_id, "job_id": None, "status": "rejected", "score": 0, "is_duplicate": False}

    job = db_session.query(Job).filter(Job.id == candidate.job_id).first()
    if not job:
        logger.error("Job not found: %s (candidate %s)", candidate.job_id, candidate_id)
        candidate.status = "rejected"
        candidate.rejection_reason = f"Job {candidate.job_id} not found"
        _set_application_status(candidate_id, candidate.job_id, "rejected", db_session)
        db_session.commit()
        return {"candidate_id": candidate_id, "job_id": candidate.job_id, "status": "rejected", "score": 0, "is_duplicate": False}

    logger.info("Found job %s: title=%s, skills=%s, experience_min=%s", 
                job.id, job.title, job.skills, job.experience_min)

    # ── 3. Find application and Duplicate detection ──────────────────────────
    application = db_session.query(Application).filter(
        Application.candidate_id == candidate_id,
        Application.job_id == candidate.job_id,
    ).first()
    try:
        is_dup, original_id = check_duplicate(candidate, db_session)
    except Exception as e:
        logger.exception("Duplicate detection failed for %s: %s", candidate_id, e)
        is_dup, original_id = False, None

    if is_dup:
        candidate.is_duplicate = True
        candidate.merged_into = original_id
        candidate.status = "rejected"
        candidate.rejection_reason = f"Duplicate of candidate {original_id}"
        _set_application_status(candidate_id, candidate.job_id, "rejected", db_session)
        db_session.commit()
        logger.info("Candidate %s marked as duplicate of %s", candidate_id, original_id)
        return {
            "candidate_id": candidate_id,
            "job_id": candidate.job_id,
            "application_id": application.id if application else None,
            "status": "rejected",
            "score": 0,
            "is_duplicate": True,
        }

    # ── 4. Score candidate ────────────────────────────────────────────────────
    try:
        total_score, breakdown = calculate_score(candidate, job)
    except Exception as e:
        logger.exception("Scoring failed for %s: %s", candidate_id, e)
        candidate.status = "rejected"
        candidate.rejection_reason = f"Scoring error: {str(e)}"
        _set_application_status(candidate_id, candidate.job_id, "rejected", db_session)
        db_session.commit()
        return {"candidate_id": candidate_id, "job_id": candidate.job_id, "status": "rejected", "score": 0, "is_duplicate": False}

    # ── 5. Decide status ──────────────────────────────────────────────────────
    if total_score >= SHORTLIST_THRESHOLD:
        status = "shortlisted"
        rejection_reason = None
    else:
        status = "rejected"
        rejection_reason = f"Score {total_score} below threshold {SHORTLIST_THRESHOLD}"

    # ── 6. Update DB ─────────────────────────────────────────────────────────
    candidate.score = total_score
    candidate.score_breakdown = json.dumps(breakdown)
    candidate.status = status
    candidate.rejection_reason = rejection_reason
    _set_application_status(candidate_id, candidate.job_id, status, db_session)
    db_session.commit()

    logger.info(
        "Candidate %s processed: status=%s score=%d job_id=%s",
        candidate_id, status, total_score, candidate.job_id,
    )

    return {
        "candidate_id": candidate_id,
        "job_id": candidate.job_id,
        "application_id": application.id if application else None,
        "status": status,
        "score": total_score,
        "is_duplicate": False,
    }
