"""
Candidate-Job Linker Utility
Fixes candidates that don't have job_id set by linking them through Application records.
"""
import logging
from sqlalchemy import select
from shared.db.models import Candidate, Application, Job

logger = logging.getLogger(__name__)


def link_candidates_to_jobs(db_session):
    """
    Find candidates without job_id and link them through Application records.
    
    Args:
        db_session: Active SQLAlchemy session
        
    Returns:
        dict with counts of linked and unlinked candidates
    """
    # Find candidates without job_id
    candidates_without_job = db_session.query(Candidate).filter(
        Candidate.job_id.is_(None)
    ).all()
    
    linked_count = 0
    unlinked_count = 0
    
    for candidate in candidates_without_job:
        # Find application for this candidate
        application = db_session.query(Application).filter(
            Application.candidate_id == candidate.id
        ).first()
        
        if application and application.job_id:
            # Verify job exists
            job = db_session.query(Job).filter(Job.id == application.job_id).first()
            if job:
                candidate.job_id = application.job_id
                linked_count += 1
                logger.info("Linked candidate %s to job %s (%s)", 
                           candidate.id, job.id, job.title)
            else:
                logger.warning("Job %s not found for candidate %s", 
                              application.job_id, candidate.id)
                unlinked_count += 1
        else:
            logger.warning("No application found for candidate %s", candidate.id)
            unlinked_count += 1
    
    if linked_count > 0:
        db_session.commit()
        logger.info("Successfully linked %d candidates to jobs", linked_count)
    
    return {
        "linked": linked_count,
        "unlinked": unlinked_count,
        "total_processed": len(candidates_without_job)
    }


def ensure_candidate_job_link(candidate_id, db_session):
    """
    Ensure a specific candidate has job_id set.
    
    Args:
        candidate_id: UUID of candidate to check
        db_session: Active SQLAlchemy session
        
    Returns:
        bool: True if candidate has job_id, False otherwise
    """
    candidate = db_session.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        logger.error("Candidate %s not found", candidate_id)
        return False
    
    if candidate.job_id:
        return True
    
    # Try to find job_id through Application
    application = db_session.query(Application).filter(
        Application.candidate_id == candidate_id
    ).first()
    
    if application and application.job_id:
        # Verify job exists
        job = db_session.query(Job).filter(Job.id == application.job_id).first()
        if job:
            candidate.job_id = application.job_id
            db_session.flush()
            logger.info("Linked candidate %s to job %s", candidate_id, job.id)
            return True
    
    logger.warning("Could not link candidate %s to any job", candidate_id)
    return False