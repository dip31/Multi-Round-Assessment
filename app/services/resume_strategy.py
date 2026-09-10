"""
Resume processing strategy abstraction.

Provides a clean interface for different resume processing implementations
(demo synchronous vs production Celery) without scattering deployment-mode
checks throughout the codebase.
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings as settings_module
from app.models.resume_processing import ResumeProcessingJob
from app.services.groq_service import GroqService
from app.services.resume_processor import ProcessingResult, ResumeProcessor
from app.services.storage import get_storage_client

logger = logging.getLogger(__name__)


@dataclass
class StrategyResult:
    """Result from a processing strategy."""
    job_id: int
    status: str  # "completed" | "failed" | "enqueued"
    pool_id: Optional[int] = None
    error_message: Optional[str] = None


class ResumeProcessingStrategy(ABC):
    """Abstract base class for resume processing strategies."""

    @abstractmethod
    def process(self, job: ResumeProcessingJob, file_bytes: bytes) -> StrategyResult:
        """Process a resume and return the result."""
        pass

    @abstractmethod
    def get_strategy_name(self) -> str:
        """Return the strategy name for logging/debugging."""
        pass


class SyncResumeProcessor(ResumeProcessingStrategy):
    """Demo mode: synchronous in-process processing with local temp storage."""

    def __init__(self, db: Session, groq_service: GroqService):
        self.db = db
        self.processor = ResumeProcessor(db, groq_service)

    def process(self, job: ResumeProcessingJob, file_bytes: bytes) -> StrategyResult:
        """Process resume synchronously using local temp storage."""
        # Get local storage client
        storage = get_storage_client(bucket_type="resumes")

        if storage is None:
            # This should not happen in demo mode since factory returns LocalStorageClient
            logger.error("Local storage not available for demo mode")
            return self._mark_failed(job, "storage_unavailable", "Local storage not configured")

        # Store file in local temp storage
        temp_key = f"temp_{job.id}_{uuid.uuid4().hex}.pdf"
        try:
            storage.put("resumes", temp_key, file_bytes, content_type="application/pdf")
            logger.debug("Stored temp resume for job %s at key %s", job.id, temp_key)

            # Read back from storage (ensures storage round-trip works)
            stored_bytes = storage.get("resumes", temp_key)

            # Process using shared logic
            result = self.processor.process_resume_bytes(stored_bytes, job)

            return StrategyResult(
                job_id=job.id,
                status="completed",
                pool_id=result.pool_id,
            )

        except Exception as e:
            logger.exception("Sync resume processing failed for job %s", job.id)
            # Mark job as failed
            error_type = getattr(e, 'error_type', 'pipeline')
            error_message = str(e)
            self.processor.mark_job_failed(job, error_type, error_message)
            return StrategyResult(
                job_id=job.id,
                status="failed",
                error_message=error_message,
            )
        finally:
            # ALWAYS cleanup temp file
            try:
                storage.delete("resumes", temp_key)
                logger.debug("Cleaned up temp resume for job %s", job.id)
            except Exception as cleanup_error:
                logger.warning("Failed to cleanup temp file for job %s: %s", job.id, cleanup_error)

    def _mark_failed(self, job: ResumeProcessingJob, error_type: str, message: str) -> StrategyResult:
        """Helper to mark job as failed."""
        self.processor.mark_job_failed(job, error_type, message)
        return StrategyResult(
            job_id=job.id,
            status="failed",
            error_message=message,
        )

    def get_strategy_name(self) -> str:
        return "sync"


class CeleryResumeProcessor(ResumeProcessingStrategy):
    """Production mode: enqueue to Celery worker for async processing."""

    def __init__(self, db: Session, groq_service: GroqService):
        self.db = db
        # GroqService not used directly but kept for interface consistency

    def process(self, job: ResumeProcessingJob, file_bytes: bytes) -> StrategyResult:
        """Enqueue resume processing to Celery worker.

        Note: file_bytes is already uploaded to GCS by the caller (async_resume_router).
        We only need to enqueue the task with job_id and storage_key.
        """
        try:
            # Import lazily to avoid Celery dependency at module load time
            from app.worker.tasks import process_resume_job
            process_resume_job.delay(job_id=job.id, storage_key=job.storage_key)
            logger.info("Enqueued resume processing job %s to Celery", job.id)
            return StrategyResult(
                job_id=job.id,
                status="enqueued",
            )
        except Exception as e:
            logger.exception("Failed to enqueue Celery task for job %s", job.id)
            # Mark job as failed
            job.status = "FAILED"
            job.error_message = "Could not queue resume for processing. Please retry."
            job.completed_at = datetime.utcnow()
            self.db.commit()
            return StrategyResult(
                job_id=job.id,
                status="failed",
                error_message="Could not queue resume for processing. Please retry.",
            )

    def get_strategy_name(self) -> str:
        return "celery"


def get_resume_processing_strategy(
    db: Session,
    groq_service: GroqService,
) -> ResumeProcessingStrategy:
    """Factory returning the appropriate strategy based on DEPLOYMENT_MODE."""
    settings = settings_module.settings
    if settings.is_demo:
        return SyncResumeProcessor(db, groq_service)
    else:
        return CeleryResumeProcessor(db, groq_service)