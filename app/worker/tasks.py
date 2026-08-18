"""
Celery task registry.

All Celery tasks for the platform live here and are imported by the worker
startup only (see ``scripts/start_worker`` or ``celery -A app.worker``).

Stage 5 shipped only the no-op health-check task. Stage 6A adds
``process_resume_job`` which is the worker-side of the async resume
pipeline. It:

    1. loads job_id from resume_processing_jobs
    2. sets status=PROCESSING with retry_count += 1
    3. downloads the resume bytes from MinIO using storage_key
    4. REUSES the existing synchronous resume-parsing services
       (parse_resume + groq.generate_question_pool) — does NOT duplicate /
       rewrite the pipeline
    5. creates an ApprovedQuestionPool row (same one the sync endpoint creates)
    6. marks status=COMPLETED with pool_id/role metadata on the job row
    7. on unrecoverable error: marks FAILED with a safe user-facing message

Retry model:
- Celery's ``self.retry`` is used ONLY for transient infrastructure failures
  — MinIO 5xx, DB connection blips, broker hiccups. Bounded by max_retries=3.
- Non-transient failures (invalid file content, empty PDF, JSON parse errors
  caught by the existing pipeline) immediately mark the job FAILED. The
  worker does NOT retry indefinitely on a structurally-bad resume.
- ``retry_count`` on the job row is incremented on EVERY attempt (including
  the first), so the operator-facing counter reflects total attempts.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


# Safe user-facing messages — NEVER include stack trace text or internal
# service names that could leak implementation detail.
_SOFT_FAILURE_MESSAGES = {
    "unparsable": "We couldn't read your resume. Make sure it's a valid, text-based PDF (not a scan).",
    "empty": "The uploaded file appears to be empty.",
    "pipeline": "We couldn't analyze your resume. Please upload a different file.",
}


@celery_app.task(
    name="app.worker.tasks.health_check",
    bind=True,
    max_retries=None,  # never retry the health probe
)
def health_check(self) -> dict:
    """No-op task used to verify the broker and worker are wired."""
    return {"status": "ok", "worker": "alive", "eager": celery_app.conf.task_always_eager}


# Lies the worker will use to detect transient vs housing vs application
# failures. We import StorageError lazily inside the task body so importing
# this module does NOT require the storage module at boot in tests where
# MinIO isn't configured.
# Retry policy: max 3 attempts, exponential-ish backoff (Celery default is
# fixed count down between attempts — explicit countdown below).
MAX_RESUME_PROCESSING_RETRIES = 3
RESUME_RETRY_COUNTDOWN_SECONDS = 30  # set on Celery retry


def _classify_error(exc: BaseException, *, e_type: Optional[str] = None) -> tuple[str, str, bool]:
    """Return (safe_message, message_key, is_transient).

    is_transient=True => re-queue via self.retry
    is_transient=False => final FAILED status with safe_message
    """
    # Lazy imports to avoid StorageError at boot when STORAGE_BACKEND=none.
    try:
        from app.services.storage.base import StorageError
    except Exception:  # pragma: no cover — only if storage package gone
        StorageError = RuntimeError  # type: ignore[assignment]

    if isinstance(exc, StorageError):
        return ("Resume storage is temporarily unavailable. Retry shortly.",
                "storage_transient", True)
    if e_type == "minio_get_failed":
        return ("Resume storage is temporarily unavailable. Retry shortly.",
                "storage_get", True)
    if e_type == "db_transient":
        return ("Backend services are temporarily unavailable. Retry shortly.",
                "db_transient", True)
    if e_type == "unparsable":
        return (_SOFT_FAILURE_MESSAGES["unparsable"], "unparsable", False)
    if e_type == "empty":
        return (_SOFT_FAILURE_MESSAGES["empty"], "empty", False)
    # Default: treat as a non-transient application error.
    return (_SOFT_FAILURE_MESSAGES["pipeline"], "pipeline", False)


@celery_app.task(
    name="app.worker.tasks.process_resume_job",
    bind=True,
    max_retries=MAX_RESUME_PROCESSING_RETRIES,
)
def process_resume_job(self, *, job_id: int, storage_key: str) -> Dict[str, Any]:
    """Worker entry point: pull the file from MinIO and reuse the sync pipeline.

    Carries ONLY ``job_id`` + ``storage_key``. NEVER receives raw bytes.
    """
    # Lazy imports — keeps the worker process startup light, and lets tests
    # monkeypatch the parser/groq/storage without dragging heavy deps.
    from app.database.db import SessionLocal
    from app.services.storage import get_storage_client
    from app.services.resume_service import parse_resume
    from app.services.groq_service import GroqService
    from app.config.settings import settings
    from app.models.resume_processing import ResumeProcessingJob
    from app.models.interview import ApprovedQuestionPool
    from app.services.proctoring_logger import log_violation  # noqa: F401

    db = SessionLocal()
    try:
        return _run_resume_processing(self, db, job_id, storage_key, settings)
    finally:
        db.close()


def _run_resume_processing(self_task_obj, db, job_id: int, storage_key: str, settings) -> Dict[str, Any]:
    """Body split out so unit tests can call it directly with a fake DB and
    fakes for storage/parser/groq without spinning up Celery/Redis.
    """
    from app.models.resume_processing import ResumeProcessingJob
    from app.services.storage import get_storage_client

    job = db.query(ResumeProcessingJob).filter(ResumeProcessingJob.id == job_id).first()
    if job is None:
        logger.error("process_resume_job: job_id=%s not found", job_id)
        return {"job_id": job_id, "outcome": "missing"}

    # Already terminal — idempotent no-op. (Worker retried after we already
    # completed/failed. Safe because parse+insert-pool must be idempotent by
    # storage_key — see ApprovedQuestionPool creation below.)
    if job.status == "COMPLETED":
        return {"job_id": job_id, "outcome": "already_completed"}
    if job.status == "FAILED":
        return {"job_id": job_id, "outcome": "already_failed"}

    # Mark PROCESSING + increment retry_count so we never silently double-
    # process. started_at is set on the first attempt only.
    job.status = "PROCESSING"
    job.retry_count = (job.retry_count or 0) + 1
    if job.started_at is None:
        from datetime import datetime
        job.started_at = datetime.utcnow()
    job.progress_step = "claiming"
    db.commit()
    db.refresh(job)

    # ── IDEMPOTENCY SHORT-CIRCUIT (Stage 6B) ─────────────────────────
    # If a previous attempt committed an ApprovedQuestionPool AND wrote
    # job_metadata.pool_id in the same transaction, we can short-circuit
    # straight to COMPLETED without re-fetching bytes, re-parsing, or
    # re-running Groq. This eliminates the duplicate-pool risk entirely.
    meta = dict(job.job_metadata or {})
    existing_pool_id = meta.get("pool_id")
    if existing_pool_id is not None:
        from app.models.interview import ApprovedQuestionPool
        existing_pool = db.query(ApprovedQuestionPool).filter(
            ApprovedQuestionPool.id == existing_pool_id
        ).first()
        if existing_pool is not None:
            # Reuse the previously-created pool; mark COMPLETED in one commit.
            from datetime import datetime
            job.status = "COMPLETED"
            job.progress_step = "done"
            job.completed_at = datetime.utcnow()
            job.error_message = None
            final_meta = dict(meta)
            final_meta.setdefault("detected_role", existing_pool.detected_role or "SDE")
            final_meta.setdefault("question_count", len(existing_pool.question_pool or []))
            job.job_metadata = final_meta
            db.commit()
            return {
                "job_id": job_id,
                "outcome": "completed",
                "pool_id": existing_pool.id,
                "detected_role": final_meta.get("detected_role"),
                "question_count": final_meta.get("question_count"),
            }
        # else: pool vanished (e.g. cascade-deleted). Fall through; we'll
        # re-run the full pipeline. Worst case it creates a fresh pool.

    # ── Step 1: download resume from MinIO ────────────────────────────
    storage = get_storage_client()
    if storage is None:
        # No storage backend configured at runtime — treat as transient
        # infra failure: enqueue a retry. If we exhaust retries, the
        # outer except block will mark FAILED.
        safe_msg, _, _ = _classify_error(RuntimeError("storage disabled"), e_type="db_transient")
        return _handle_failure(self_task_obj, db, job, safe_msg, RuntimeError("storage disabled"),
                               transient=True, e_type="db_transient")

    try:
        file_bytes = storage.get(settings.STORAGE_RESUMES_BUCKET, storage_key)
    except Exception as e:
        logger.exception("Storage get failed for job_id=%s key=%s", job_id, storage_key)
        safe_msg, _, _ = _classify_error(e, e_type="minio_get_failed")
        return _handle_failure(self_task_obj, db, job, safe_msg, e,
                               transient=True, e_type="minio_get_failed")

    if not file_bytes:
        # Empty object — non-transient: retry won't help, the file is bad.
        safe_msg, _, _ = _classify_error(ValueError("empty"), e_type="empty")
        return _handle_failure(self_task_obj, db, job, safe_msg, ValueError("empty bytes"),
                               transient=False, e_type="empty")

    job.progress_step = "parsing_resume"
    db.commit()

    # ── Step 2: parse + classify using EXISTING pipeline ─────────────
    try:
        from app.services.resume_service import parse_resume
        from app.services.groq_service import GroqService

        # Use the EXISTING synchronous helper — it already handles errors
        # and returns a dict with skills/projects/experience/...
        extracted = parse_resume(file_bytes)
        # Existing parse_resume swallows exceptions and returns {skills: []}
        # when it fails. Detect empty content as a non-transient "unparsable"
        # failure so the candidate gets feedback rather than a blank pool.
        if not extracted.get("skills") and not extracted.get("full_content") and not extracted.get("projects"):
            safe_msg, _, _ = _classify_error(ValueError("unparsable"), e_type="unparsable")
            return _handle_failure(self_task_obj, db, job, safe_msg, ValueError("unparsable"),
                                   transient=False, e_type="unparsable")
    except Exception as e:
        logger.exception("parse_resume raised job_id=%s", job_id)
        safe_msg, _, _ = _classify_error(e, e_type="unparsable")
        return _handle_failure(self_task_obj, db, job, safe_msg, e,
                               transient=False, e_type="unparsable")

    job.progress_step = "generating_pool"
    db.commit()

    # ── Step 3: generate question pool — existing pipeline ───────────
    groq = GroqService(settings.GROQ_API_KEY)
    try:
        pool = groq.generate_question_pool(
            extracted["skills"],
            extracted["projects"],
            count=12,
        )
    except Exception as e:
        logger.exception("generate_question_pool raised job_id=%s", job_id)
        safe_msg, _, _ = _classify_error(e, e_type="pipeline")
        return _handle_failure(self_task_obj, db, job, safe_msg, e,
                               transient=True, e_type="pipeline")

    if not pool:
        # Empty pool — existing pipeline returns [] only on hard failure
        # (which itself logs; surface a safe message but don't retry forever).
        safe_msg, _, _ = _classify_error(ValueError("empty pool"), e_type="pipeline")
        return _handle_failure(self_task_obj, db, job, safe_msg, ValueError("empty pool"),
                               transient=False, e_type="pipeline")

    # ── Step 4: persist ApprovedQuestionPool ──────────────────────────
    detected_role = pool[0].get("role", "SDE") if pool else "SDE"
    try:
        from datetime import datetime
        from app.models.interview import ApprovedQuestionPool

        # IDEMPOTENCY (Stage 6B): same-transaction pairing of pool insert
        # + job_metadata.pool_id. The short-circuit at the top of the
        # function has already returned if metadata.pool_id was set on
        # entry; if we reach here, no pool exists yet for this job.
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
        db.add(pool_record)
        # Flush so pool_record.id is assigned, then persist BOTH the pool
        # row and the metadata pointer in the SAME transaction. If this
        # commit fails they roll back together — no orphan pool, no
        # metadata pointer to a non-existent pool.
        db.flush()
        meta = dict(job.job_metadata or {})
        meta["pool_id"] = pool_record.id
        meta["detected_role"] = detected_role
        meta["question_count"] = len(pool)
        job.job_metadata = meta
        db.commit()
        db.refresh(pool_record)
        pool_id = pool_record.id
        existing_count = len(pool)
        existing_role = detected_role
    except Exception as e:
        logger.exception("DB write failed for pool/job_id=%s", job_id)
        db.rollback()
        # Conservative: assume transient — a retry will re-enter the
        # idempotency short-circuit which is safe.
        safe_msg, _, _ = _classify_error(e, e_type="db_transient")
        return _handle_failure(self_task_obj, db, job, safe_msg, e,
                               transient=True, e_type="db_transient")

    # ── Step 5: mark COMPLETED with safe metadata ─────────────────────
    from datetime import datetime
    job.status = "COMPLETED"
    job.progress_step = "done"
    job.completed_at = datetime.utcnow()
    job.error_message = None
    # Keep metadata as it already carries pool_id from the same commit.
    final_meta = dict(job.job_metadata or {})
    final_meta.setdefault("pool_id", pool_id)
    final_meta.setdefault("detected_role", existing_role)
    final_meta.setdefault("question_count", existing_count)
    job.job_metadata = final_meta
    db.commit()

    return {
        "job_id": job_id,
        "outcome": "completed",
        "pool_id": pool_id,
        "detected_role": existing_role,
        "question_count": existing_count,
    }


def _handle_failure(self_task_obj, db, job, safe_message, exc, *, transient: bool, e_type: str):
    """Common path for failures.

    transient=True  -> re-queue via Celery self.retry (bounded by max_retries)
    transient=False -> mark the job FAILED immediately with safe_message.
    """
    from datetime import datetime
    max_retries = MAX_RESUME_PROCESSING_RETRIES

    if not transient:
        # Final failure — write FAILED and stop. Safe user-facing message
        # only; the underlying exception is logged on the worker side.
        job.status = "FAILED"
        job.progress_step = f"failed:{e_type}"
        job.error_message = safe_message
        job.completed_at = datetime.utcnow()
        db.commit()
        return {"job_id": job.id, "outcome": "failed", "reason": e_type}

    # Transient failure — retry if we haven't exhausted max_retries.
    if (job.retry_count or 0) >= max_retries:
        # Exhausted retries — final FAILED state.
        job.status = "FAILED"
        job.progress_step = f"failed_after_retries:{e_type}"
        job.error_message = safe_message
        job.completed_at = datetime.utcnow()
        db.commit()
        return {"job_id": job.id, "outcome": "failed_after_retries", "reason": e_type}

    # Persist PROCESSING (retry_count already incremented on entry) and let
    # Celery re-queue. We do NOT call self.retry when running in eager mode
    # (tests) — we just return a "pending_retry" outcome so the test can
    # assert on retry behaviour without actually waiting.
    try:
        eager_mode = celery_app.conf.task_always_eager
    except Exception:  # pragma: no cover
        eager_mode = False

    if not eager_mode and self_task_obj is not None and hasattr(self_task_obj, "retry"):
        # COMMIT before retry so the worker re-entry reads retry_count correctly.
        db.commit()
        raise self_task_obj.retry(exc=exc, countdown=RESUME_RETRY_COUNTDOWN_SECONDS)

    db.commit()
    return {"job_id": job.id, "outcome": "pending_retry", "reason": e_type}


__all__ = ["health_check", "process_resume_job"]

