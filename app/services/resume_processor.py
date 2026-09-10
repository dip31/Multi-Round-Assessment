"""
Shared resume processing logic.

This module contains the core resume processing algorithm used by BOTH
demo (synchronous) and production (Celery) modes. It encapsulates the
common logic to avoid duplication.

The service handles:
- Resume parsing via parse_resume()
- Question pool generation via GroqService
- ApprovedQuestionPool creation
- ResumeProcessingJob status updates
- Error handling with safe user-facing messages
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.interview import ApprovedQuestionPool
from app.models.resume_processing import ResumeProcessingJob
from app.services.groq_service import GroqService
from app.services.memory_diagnostics import log_memory
from app.services.resume_service import parse_resume

logger = logging.getLogger(__name__)


class ResumeProcessingError(Exception):
    """Raised when resume processing fails with a user-safe message."""
    def __init__(self, message: str, error_type: str = "pipeline"):
        super().__init__(message)
        self.error_type = error_type


@dataclass
class ProcessingResult:
    """Result of resume processing."""
    job_id: int
    pool_id: Optional[int] = None
    detected_role: Optional[str] = None
    question_count: int = 0
    error_message: Optional[str] = None
    error_type: Optional[str] = None


def _safe_failure_message(error_type: str) -> str:
    """Return user-safe error message for a given error type."""
    messages = {
        "unparsable": "We couldn't read your resume. Make sure it's a valid, text-based PDF (not a scan).",
        "empty": "The uploaded file appears to be empty.",
        "empty_pool": "We couldn't generate questions from your resume. Please try a different file.",
        "pipeline": "We couldn't analyze your resume. Please upload a different file.",
        "db_transient": "Backend services are temporarily unavailable. Please retry shortly.",
    }
    return messages.get(error_type, messages["pipeline"])


class ResumeProcessor:
    """Core resume processing logic shared by demo and production modes."""

    def __init__(self, db: Session, groq_service: GroqService):
        self.db = db
        self.groq = groq_service

    def process_resume_bytes(
        self,
        file_bytes: bytes,
        job: ResumeProcessingJob,
    ) -> ProcessingResult:
        """Process resume bytes and update job status.

        This is the single source of truth for resume processing logic.
        Used by both SyncResumeProcessor (demo) and process_resume_job task (production).

        Args:
            file_bytes: Raw PDF bytes
            job: ResumeProcessingJob row to update

        Returns:
            ProcessingResult with outcome details

        Raises:
            ResumeProcessingError: On processing failure (job status updated to FAILED)
        """
        # 1. Mark PROCESSING
        job.status = "PROCESSING"
        job.progress_step = "parsing_resume"
        if job.started_at is None:
            job.started_at = datetime.utcnow()
        job.retry_count = (job.retry_count or 0) + 1
        self.db.commit()
        self.db.refresh(job)

        # 2. Parse resume
        try:
            extracted = parse_resume(file_bytes)
            if not extracted.get("skills") and not extracted.get("projects") and not extracted.get("full_content"):
                raise ResumeProcessingError(
                    _safe_failure_message("unparsable"),
                    error_type="unparsable"
                )
            log_memory("after skill/project extraction")
        except ResumeProcessingError:
            raise
        except Exception as e:
            logger.exception("parse_resume raised for job_id=%s", job.id)
            raise ResumeProcessingError(
                _safe_failure_message("unparsable"),
                error_type="unparsable"
            ) from e

        job.progress_step = "generating_pool"
        self.db.commit()

        # 3. Generate question pool
        try:
            pool = self.groq.generate_question_pool(
                extracted["skills"],
                extracted["projects"],
                count=12,
            )
        except Exception as e:
            logger.exception("generate_question_pool raised for job_id=%s", job.id)
            raise ResumeProcessingError(
                _safe_failure_message("pipeline"),
                error_type="pipeline"
            ) from e

        if not pool:
            raise ResumeProcessingError(
                _safe_failure_message("empty_pool"),
                error_type="empty_pool"
            )

        # 4. Create ApprovedQuestionPool
        detected_role = pool[0].get("role", "SDE") if pool else "SDE"
        try:
            log_memory("before DB save")
            pool_record = ApprovedQuestionPool(
                session_id=job.session_id,
                extracted_skills=extracted["skills"],
                extracted_projects=extracted["projects"],
                question_pool=pool,
                admin_approved=True,
                approved_by=None,
                approved_at=datetime.now(),
                detected_role=detected_role,
            )
            self.db.add(pool_record)
            # Flush to get pool_record.id
            self.db.flush()

            # Update job metadata with pool info
            meta = dict(job.job_metadata or {})
            meta["pool_id"] = pool_record.id
            meta["detected_role"] = detected_role
            meta["question_count"] = len(pool)
            job.job_metadata = meta

            # 5. Mark COMPLETED
            job.status = "COMPLETED"
            job.progress_step = "done"
            job.completed_at = datetime.utcnow()
            job.error_message = None
            self.db.commit()
            log_memory("after DB save")

            return ProcessingResult(
                job_id=job.id,
                pool_id=pool_record.id,
                detected_role=detected_role,
                question_count=len(pool),
            )

        except Exception as e:
            logger.exception("DB write failed for pool/job_id=%s", job.id)
            self.db.rollback()
            raise ResumeProcessingError(
                _safe_failure_message("db_transient"),
                error_type="db_transient"
            ) from e

    def mark_job_failed(
        self,
        job: ResumeProcessingJob,
        error_type: str,
        error_message: Optional[str] = None,
    ) -> ProcessingResult:
        """Mark job as FAILED with safe error message."""
        safe_message = error_message or _safe_failure_message(error_type)
        job.status = "FAILED"
        job.progress_step = f"failed:{error_type}"
        job.error_message = safe_message
        job.completed_at = datetime.utcnow()
        self.db.commit()
        return ProcessingResult(
            job_id=job.id,
            error_message=safe_message,
            error_type=error_type,
        )