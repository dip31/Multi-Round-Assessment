"""
Async resume upload router (Stage 6A).

Introduces a NEW pair of endpoints that decouple HTTP upload from resume
parsing:

    POST /api/v1/interview/resume/upload-async
        - Multipart upload of the resume PDF
        - Validates type + size
        - Generates a safe storage key
        - Uploads raw bytes to MinIO via StorageClient
        - Inserts a resume_processing_jobs row with status=PENDING
        - Enqueues a Celery task carrying ONLY { job_id, storage_key }
        - Responds with { job_id, status: "PENDING" }

    GET /api/v1/interview/resume/processing/{job_id}
        - Authenticates the user
        - Verifies the user owns the job (403 otherwise)
        - Returns safe status information (no stack traces)

The existing synchronous endpoint
``POST /api/v1/interview/resume/upload`` is NOT modified. Clients can
continue calling it unchanged; it does not depend on MinIO or Celery.

Design constraints honored:
- HTTP body is READ DIRECTLY from UploadFile and only used to put bytes
  into MinIO. The raw bytes are NEVER forwarded to the worker — only the
  storage_key is. This keeps HTTP, storage, and async processing decoupled.
- No Celery import happens at module import time; enqueue is done lazily
  inside the request handler so the FastAPI app stack does not depend on
  Celery/Redis being available to serve the sync flow.
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.auth import get_current_user
from app.database.db import get_db
from app.models.assessment import AssessmentSession
from app.models.resume_processing import ResumeProcessingJob
from app.models.user import User
from app.modules.interview.schemas.interview_schema import (
    AsyncResumeUploadResponse,
    ResumeProcessingJobStatus,
)
from app.services.storage import get_storage_client

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/interview",
    tags=["Interview Round — Async Resume"],
)

# Limits — kept server-configurable so production can tune them without code
# edits. The file type restriction is intentionally narrow (PDF only) to
# match the existing sync endpoint and avoid broadening the attack surface.
ALLOWED_EXTENSIONS = {".pdf"}
# Reasonable default; typed as Settings.MAX_RESUME_SIZE_BYTES in app.config.settings.
MAX_RESUME_SIZE_BYTES: int = settings.MAX_RESUME_SIZE_BYTES
# Safe filename pattern: letters/digits/dash/underscore/dot only.
_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._-]")


def _build_storage_key(user_id: int, session_id: int, original_filename: Optional[str]) -> str:
    """Build a safe, unique storage key for the uploaded resume.

    Format: ``resumes/{user_id}/{session_id}/{uuid}.{ext}``

    The original filename is sanitized to a leaf extension; the stem is
    discarded so candidates cannot inject path separators or traversal
    sequences into the object storage key.
    """
    # Keep only the extension (lowercased) — stems are uuid-based so the key
    # is opaque to outsiders and guaranteed unique.
    ext = ".pdf"
    if original_filename:
        _, e = os.path.splitext(original_filename)
        if e and e.lower() in ALLOWED_EXTENSIONS:
            ext = e.lower()
    safe_uuid = uuid.uuid4().hex
    return f"resumes/{user_id}/{session_id}/{safe_uuid}{ext}"


def _validate_upload(file: Optional[UploadFile]) -> None:
    """Raise HTTPException with 400/413 on validation failure.

    Done as a helper so tests can call it directly without spinning FastAPI.
    """
    if not file or not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="File must be a PDF",
        )


def _read_and_validate_size(file: UploadFile) -> bytes:
    """Read the multipart body and validate size against MAX_RESUME_SIZE_BYTES.

    Streaming read with a hard cap so a maliciously large upload cannot
    exhaust memory before validation rejects it.
    """
    # Caller must already be inside an async endpoint. We are. We mark this
    # helper as a plain function returning bytes; the actual ``await
    # file.read()`` happens in the async handler so this function is intentionally
    # not async (it would be a Python footgun to nest awaits).
    raise RuntimeError("_read_and_validate_size must not be called directly; use _read_and_validate_size_async.")


async def _read_and_validate_size_async(file: UploadFile) -> bytes:
    """Async implementation: stream up to MAX_RESUME_SIZE_BYTES+1 and validate."""
    content = bytearray()
    chunk_size = 64 * 1024
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > MAX_RESUME_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Resume exceeds maximum size of {MAX_RESUME_SIZE_BYTES} bytes",
            )
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    return bytes(content)


# ── ENDPOINT: POST /api/v1/interview/resume/upload-async ──────────────
@router.post(
    "/resume/upload-async",
    response_model=AsyncResumeUploadResponse,
)
async def upload_resume_async(
    file: UploadFile = File(...),
    session_id: Optional[int] = Query(None, description="Assessment session ID (optional)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a resume PDF and enqueue asynchronous processing.

    Steps:
      1. Authenticate the user (via ``get_current_user``).
      2. Validate file type and size.
      3. Determine assessment session_id (explicit or latest in_progress).
      4. Generate a safe storage_key.
      5. Upload raw bytes to MinIO via StorageClient.
      6. Insert a resume_processing_jobs row with status=PENDING.
      7. Enqueue the Celery worker task carrying ONLY { job_id, storage_key }.
      8. Return { job_id, status: "PENDING" } immediately.

    The original synchronous resume-upload endpoint is NOT modified.
    """
    _validate_upload(file)
    content = await _read_and_validate_size_async(file)

    # Resolve session_id (same pattern as the sync endpoint).
    if not session_id:
        active_session = (
            db.query(AssessmentSession)
            .filter(
                AssessmentSession.user_id == current_user.id,
                AssessmentSession.status == "in_progress",
            )
            .order_by(AssessmentSession.id.desc())
            .first()
        )
        if not active_session:
            raise HTTPException(
                status_code=400,
                detail="No active assessment session found. Please start an assessment first.",
            )
        session_id = active_session.id

    storage = get_storage_client()
    if storage is None:
        # MinIO not configured. We fail loud here because the async flow
        # cannot work without object storage — silent fallback would let the
        # candidate believe the upload succeeded.
        raise HTTPException(
            status_code=503,
            detail="Object storage is not configured. Resume upload unavailable.",
        )

    storage_key = _build_storage_key(current_user.id, session_id, file.filename)
    try:
        storage.put(
            settings.STORAGE_RESUMES_BUCKET,
            storage_key,
            content,
            content_type="application/pdf",
        )
    except Exception as e:
        # Log full exception with stack for ops; surface only safe text.
        logger.exception("Storage put failed for user_id=%s session_id=%s", current_user.id, session_id)
        raise HTTPException(
            status_code=503,
            detail="Failed to store resume. Please try again shortly.",
        ) from e

    # Create the job row. Only the safe fields from the upload appear here —
    # no error_state; the row starts life PENDING.
    job = ResumeProcessingJob(
        user_id=current_user.id,
        session_id=session_id,
        storage_key=storage_key,
        original_filename=_sanitize_filename(file.filename),
        status="PENDING",
        progress_step="uploaded",
        retry_count=0,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Enqueue the worker task lazily so web-serving does not import Celery
    # at boot. The task carries ONLY { job_id, storage_key } — never bytes.
    try:
        from app.worker.tasks import process_resume_job
        process_resume_job.delay(job_id=job.id, storage_key=storage_key)
    except Exception as e:
        # If the broker is unreachable we mark the job FAILED with a safe
        # message rather than leaving it stuck in PENDING forever. The
        # candidate sees a friendly error in the status endpoint.
        logger.exception("Enqueue failed for job_id=%s", job.id)
        job.status = "FAILED"
        job.error_message = "Could not queue resume for processing. Please retry."
        db.commit()
        raise HTTPException(
            status_code=503,
            detail="Could not queue resume for processing. Please retry.",
        ) from e

    return AsyncResumeUploadResponse(job_id=job.id, status="PENDING")


def _sanitize_filename(name: Optional[str]) -> str:
    """Strip path separators / control chars from a user-supplied filename.

    Stored purely for diagnostics in the job row; the actual storage key
    never uses this. Length-capped at 255 so it fits the column.
    """
    if not name:
        return "resume.pdf"
    cleaned = _SAFE_FILENAME_RE.sub("_", os.path.basename(name))
    return cleaned[:255] or "resume.pdf"


# ── ENDPOINT: GET /api/v1/interview/resume/processing/{job_id} ─────────
@router.get(
    "/resume/processing/{job_id}",
    response_model=ResumeProcessingJobStatus,
)
async def get_resume_processing_status(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return safe resume-processing job status, scoped to the requesting user.

    Access control: if ``job.user_id != current_user.id`` AND user is not
    admin, returns 404 (NOT 403) so candidates cannot enumerate other
    candidates' job IDs. This is the standard "information hiding" pattern.

    Returns only safe fields — never stack traces, never internal paths.
    """
    job = (
        db.query(ResumeProcessingJob)
        .filter(ResumeProcessingJob.id == job_id)
        .first()
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Resume processing job not found")

    # Note: non-admin users querying someone else's job get 404, not 403,
    # to avoid information leak about whose IDs are in use.
    if job.user_id != current_user.id and getattr(current_user, "role", None) != "admin":
        raise HTTPException(status_code=404, detail="Resume processing job not found")

    # Detach role/pool info from job_metadata (worker writes it on COMPLETED).
    meta = job.job_metadata or {}
    return ResumeProcessingJobStatus(
        job_id=job.id,
        status=job.status,
        progress_step=job.progress_step,
        detected_role=meta.get("detected_role"),
        pool_id=meta.get("pool_id"),
        question_count=meta.get("question_count"),
        error_message=job.error_message,
        created_at=job.created_at.isoformat() if job.created_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )
