"""
Interview Round Router

Handles all HTTP endpoints related to the Interview Round.

Endpoints:
- POST /interview/resume/upload - Upload resume and generate question pool
- GET /interview/pool/{pool_id} - Get approved question pool
- PUT /interview/pool/{pool_id}/approve - Approve/reject question pool
- POST /interview/session/start - Start interview session
- GET /interview/session/{interview_id}/next - Get next question (initial load only)
- POST /interview/session/{interview_id}/respond - Submit response (10-step pipeline)
- POST /interview/stt - Speech-to-text
- POST /interview/tts - Text-to-speech
- GET /interview/session/{interview_id}/report - Get interview report
"""

import hashlib
import json
import logging
import tempfile
from copy import deepcopy
from datetime import datetime
from typing import Optional

import redis
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.config.settings import settings
from app.core.auth import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.models.profile import UserResume
from app.models.interview import (
    InterviewSession,
    ApprovedQuestionPool,
    InterviewTurn,
)
from app.models.assessment import AssessmentSession
from app.services.resume_service import parse_resume
from app.services.groq_service import GroqService
from app.services.assessment_blueprint_service import (
    configured_question_count,
    get_session_active_blueprint_round_config,
)
from app.modules.interview.schemas.interview_schema import (
    ResumeUploadResponse,
    QuestionPoolResponse,
    ApprovePoolRequest,
    ApprovePoolResponse,
    StartInterviewResponse,
    NextQuestionResponse,
    SubmitResponseRequest,
    SubmitResponseResponse,
    STTResponse,
    InterviewReportResponse,
    TurnReviewItem,
    FollowupItem,
    BehavioralSnapshot,
    NextQuestionInfo,
    ScoresInfo,
    InterviewSummaryInfo,
    RealtimeFeedbackRequest,
    RealtimeFeedbackResponse,
)
from app.modules.interview.services.interview_rl_engine import InterviewRLEngine
from app.services.phone_detection_service import detect_phones
from app.services.proctoring_logger import log_violation
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/interview",
    tags=["Interview Round"],
)

# Lazy import to avoid circular deps — only used in completion hooks
def _try_advance_mock_drive(db, session_id):
    try:
        from app.services.mock_drive_service import try_advance_mock_drive
        return try_advance_mock_drive(db, session_id)
    except Exception:
        return None


# ── Candidate isolation helpers ───────────────────────────────────────
# Staff roles allowed to READ candidate interview data, matching the existing
# /interview/report frontend route (student/faculty/tpo/admin) and the report
# module's role policy. Write actions remain owner-only.
_STAFF_ROLES = ("admin", "faculty", "tpo")


def _assessment_session_owner_id(db: Session, assessment_session_id: Optional[int]) -> Optional[int]:
    """Return the user id owning an AssessmentSession, or None if not found."""
    if assessment_session_id is None:
        return None
    assessment_session = (
        db.query(AssessmentSession)
        .filter(AssessmentSession.id == assessment_session_id)
        .first()
    )
    return assessment_session.user_id if assessment_session else None


def _get_interview_for_user(
    db: Session,
    interview_id: int,
    current_user: User,
    *,
    allow_staff: bool = True,
) -> InterviewSession:
    """Return the interview session, enforcing candidate isolation.

    The owning candidate always has access; staff roles may read when
    ``allow_staff`` is set. Any other caller receives the same 404 as a
    missing interview so another student's data (or even its existence) is
    never exposed.
    """
    interview = (
        db.query(InterviewSession)
        .filter(InterviewSession.id == interview_id)
        .first()
    )
    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found")

    owner_id = _assessment_session_owner_id(db, interview.session_id)
    if owner_id == current_user.id:
        return interview
    if allow_staff and current_user.role in _STAFF_ROLES:
        return interview
    raise HTTPException(status_code=404, detail="Interview not found")


def _require_session_owner(db: Session, assessment_session_id: int, current_user: User) -> None:
    """Ensure the caller owns the given AssessmentSession (404 otherwise)."""
    owner_id = _assessment_session_owner_id(db, assessment_session_id)
    if owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Assessment session not found")


def _require_interview_not_expired(db: Session, interview: InterviewSession) -> None:
    """Server-authoritative deadline enforcement for interview work (Phase 4C Part 3).

    Only the persisted deadlines are consulted (``AssessmentSession.expires_at``
    and the active interview ``AssessmentRound.expires_at``); client-supplied
    timing is never used. When either deadline has passed the records are
    persisted as ``expired`` with TIME_EXPIRED completion reason, the mock
    drive is advanced (if applicable), and the caller receives HTTP 410.
    Sessions without a persisted deadline (legacy / blueprintless) are left
    untouched so their behavior stays backward compatible.
    """
    from app.models.assessment import AssessmentRound, AssessmentSession
    from app.services.mock_drive_service import try_advance_mock_drive

    now = datetime.utcnow()
    assessment_session = (
        db.query(AssessmentSession)
        .filter(AssessmentSession.id == interview.session_id)
        .first()
    )
    interview_round = (
        db.query(AssessmentRound)
        .filter(
            AssessmentRound.session_id == interview.session_id,
            AssessmentRound.round_type == "interview",
            AssessmentRound.status == "active",
        )
        .order_by(AssessmentRound.id.desc())
        .first()
    )

    session_expired = (
        assessment_session is not None
        and assessment_session.expires_at is not None
        and assessment_session.expires_at <= now
    )
    round_expired = (
        interview_round is not None
        and interview_round.expires_at is not None
        and interview_round.expires_at <= now
    )
    if not session_expired and not round_expired:
        return

    if round_expired:
        interview_round.status = "expired"
        interview_round.completed_at = now
        # Set TIME_EXPIRED completion reason on the interview session
        if interview.completion_reason is None:
            interview.completion_reason = "TIME_EXPIRED"
            interview.completed_at = now
            interview.status = "COMPLETED"
    if session_expired and assessment_session.status == "in_progress":
        assessment_session.status = "expired"
        assessment_session.completed_at = now
        # Session authority: like _expire_stale_session, close every active
        # round for this session so no work remains active after the session
        # deadline (the round deadline may still be in the future).
        db.query(AssessmentRound).filter(
            AssessmentRound.session_id == assessment_session.id,
            AssessmentRound.status == "active",
        ).update(
            {"status": "expired", "completed_at": now},
            synchronize_session="fetch",
        )
        if interview.completion_reason is None:
            interview.completion_reason = "TIME_EXPIRED"
            interview.completed_at = now
            interview.status = "COMPLETED"
    db.commit()

    # Advance mock drive if this interview was part of a mock drive
    if assessment_session is not None:
        try:
            try_advance_mock_drive(db, interview.session_id)
        except HTTPException:
            pass

    raise HTTPException(
        status_code=410,
        detail="This interview has expired and has been finalized. The mock drive has advanced to the next round or completed.",
    )


class LogEventRequest(BaseModel):
    session_id: int
    event_type: str
    confidence_score: float | None = None
    face_count: int | None = None
    metadata: dict | None = None

# Global instances (will be set by app lifespan)
ml_models = {}  # To be populated by app/main.py
groq_service = GroqService(settings.GROQ_API_KEY)

# Warn at startup if GROQ_API_KEY is missing or looks like a placeholder
_groq_key = settings.GROQ_API_KEY or ""
if not _groq_key or len(_groq_key) < 30 or not _groq_key.startswith("gsk_"):
    logger.warning(
        "GROQ_API_KEY appears to be missing or invalid (expected format: gsk_..., length ~56). "
        "Interview question generation will use fallback questions. "
        "Set a real GROQ_API_KEY in .env to enable AI-generated questions."
    )

redis_client: Optional[redis.Redis] = None


def _get_redis_client() -> Optional[redis.Redis]:
    """Lazily initialize Redis so the interview flow still works without Docker."""
    global redis_client

    if redis_client is not None:
        return redis_client

    redis_url = settings.REDIS_URL
    if not redis_url:
        logger.info("Redis cache disabled: REDIS_URL not configured")
        return None
    try:
        client = redis.from_url(redis_url, decode_responses=False)
        client.ping()
        redis_client = client
        logger.info("Redis cache connected for interview question caching")
        return redis_client
    except Exception as e:
        logger.info(f"Redis cache unavailable; continuing without cache: {str(e)}")
        redis_client = None
        return None


def _generate_question_pool_for_session(
    db: Session,
    session_id: int,
    skills: list[str],
    projects: dict,
    interview_type: str,
) -> tuple[list[dict], int, bool]:
    fallback_round = (
        "hr_interview"
        if (interview_type or "").lower().strip() == "hr"
        else "technical_interview"
    )
    snapshot, round_config, round_key = get_session_active_blueprint_round_config(
        db, session_id, fallback_round
    )
    if snapshot is not None and round_config is not None:
        # Blueprint-backed interview: require the pre-generated, validated pool.
        # NO LLM call and NO generic fallback at candidate time.
        from app.services.question_pool_generation_service import (
            question_pool_generation_service,
        )

        count = configured_question_count(round_config) or 12
        generated_pool = question_pool_generation_service.complete_pool_for_round(
            db,
            snapshot.get("blueprint_id"),
            snapshot.get("blueprint_version"),
            round_key,
        )
        if generated_pool is not None and generated_pool.content:
            return deepcopy(generated_pool.content)[:count], count, True

        # Pool is missing, incomplete, or invalid — fail closed per G1.
        # No candidate-time LLM generation or generic fallback.
        raise HTTPException(
            status_code=422,
            detail=(
                f"A validated {round_key} question pool must be generated for this "
                "blueprint before starting an interview. Please generate and approve "
                "the pool in the TPO portal, then retry."
            ),
        )

    # Legacy / blueprintless interview: retain existing LLM-generation behavior.
    if snapshot is None or round_config is None:
        return (
            groq_service.generate_question_pool(
                skills,
                projects,
                count=12,
                interview_type=interview_type or "technical",
            ),
            12,
            False,
        )

    # Unreachable — blueprint-backed path returns or raises above.
    # Kept for type checkers.
    raise HTTPException(
        status_code=422,
        detail="Interview pool unavailable for this blueprint and round.",
    )


# ── ENDPOINT 1: POST /interview/resume/upload ──────────────────────────
@router.post("/resume/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    session_id: Optional[int] = Query(None, description="Assessment session ID (optional)"),
    interview_type: Optional[str] = Query("technical", description="technical | hr | communication"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload resume (PDF) and generate personalized question pool."""

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    if not session_id:
        active_session = db.query(AssessmentSession).filter(
            AssessmentSession.user_id == current_user.id,
            AssessmentSession.status == "in_progress"
        ).order_by(AssessmentSession.id.desc()).first()

        if not active_session:
            raise HTTPException(
                status_code=400,
                detail="No active assessment session found. Please start an assessment first.",
            )
        session_id = active_session.id

    # Never attach a generated pool to a session the caller does not own.
    _require_session_owner(db, session_id, current_user)

    content = None
    try:
        content = await file.read()
        extracted = parse_resume(content)
        pool, _, _ = _generate_question_pool_for_session(
            db=db,
            session_id=session_id,
            skills=extracted["skills"],
            projects=extracted["projects"],
            interview_type=interview_type or "technical",
        )

        # Extract detected_role from generated pool
        detected_role = "SDE"
        if pool and len(pool) > 0:
            detected_role = pool[0].get("role", "SDE")

        pool_record = ApprovedQuestionPool(
            session_id=session_id,
            extracted_skills=extracted["skills"],
            extracted_projects=extracted["projects"],
            question_pool=pool,
            admin_approved=True,
            approved_by=None,
            approved_at=datetime.now(),
            detected_role=detected_role
        )
        db.add(pool_record)
        db.commit()
        db.refresh(pool_record)
        return ResumeUploadResponse(
            status="pool_generated",
            pool_id=pool_record.id,
            question_count=len(pool),
            detected_role=detected_role,
            pending_approval=True,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Resume upload processing failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=(
                "Resume processing failed. "
                "Ensure the AI services are configured correctly (GROQ_API_KEY) "
                "and all required dependencies are installed."
            ),
        )
    finally:
        if content:
            del content


# ── ENDPOINT 1.1: POST /interview/resume/use-profile-resume/{resume_id} ──
@router.post("/resume/use-profile-resume/{resume_id}", response_model=ResumeUploadResponse)
async def use_profile_resume(
    resume_id: int,
    session_id: Optional[int] = Query(None, description="Assessment session ID (optional)"),
    interview_type: Optional[str] = Query("technical", description="technical | hr | communication"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate question pool using an existing uploaded resume from student profile."""
    resume = (
        db.query(UserResume)
        .filter(UserResume.id == resume_id, UserResume.user_id == current_user.id)
        .first()
    )
    if not resume:
        raise HTTPException(
            status_code=404,
            detail="Resume not found in student profile",
        )

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

    # Never attach a generated pool to a session the caller does not own.
    _require_session_owner(db, session_id, current_user)

    skills = resume.parsed_skills if isinstance(resume.parsed_skills, list) else []
    projects = resume.parsed_projects if isinstance(resume.parsed_projects, list) else []

    try:
        pool, _, _ = _generate_question_pool_for_session(
            db=db,
            session_id=session_id,
            skills=skills,
            projects=projects,
            interview_type=interview_type or "technical",
        )
    except Exception as exc:
        logger.error(f"Question pool generation failed for resume {resume_id}: {exc}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail=(
                "Question pool generation failed. "
                "Ensure GROQ_API_KEY is configured correctly."
            ),
        )

    detected_role = resume.cv_type or "Software Developer"
    if pool and len(pool) > 0 and pool[0].get("role"):
        detected_role = pool[0].get("role")

    pool_record = ApprovedQuestionPool(
        session_id=session_id,
        extracted_skills=skills,
        extracted_projects=projects,
        question_pool=pool,
        admin_approved=True,
        approved_by=None,
        approved_at=datetime.now(),
        detected_role=detected_role,
    )
    db.add(pool_record)
    db.commit()
    db.refresh(pool_record)

    return ResumeUploadResponse(
        status="pool_generated",
        pool_id=pool_record.id,
        question_count=len(pool),
        detected_role=detected_role,
        pending_approval=True,
    )


# ── ENDPOINT 1.5: GET /interview/admin/pools ──────────────────────────
@router.get("/admin/pools")
async def list_pools_for_admin(
    status: Optional[str] = Query(None, description="pending, approved, or rejected"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all question pools for admin review."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    query = db.query(
        ApprovedQuestionPool.id.label("pool_id"),
        ApprovedQuestionPool.admin_approved,
        ApprovedQuestionPool.created_at,
        User.name.label("candidate_name"),
        User.email.label("candidate_email"),
        func.jsonb_array_length(ApprovedQuestionPool.question_pool).label("question_count")
    ).join(
        AssessmentSession, ApprovedQuestionPool.session_id == AssessmentSession.id
    ).join(
        User, AssessmentSession.user_id == User.id
    )

    if status == "approved":
        query = query.filter(ApprovedQuestionPool.admin_approved == True)
    elif status == "pending":
        query = query.filter(ApprovedQuestionPool.admin_approved == False)

    pools = query.order_by(ApprovedQuestionPool.created_at.desc()).all()

    return [{
        "pool_id": p.pool_id,
        "candidate_name": p.candidate_name,
        "candidate_email": p.candidate_email,
        "created_at": p.created_at,
        "approved": p.admin_approved,
        "question_count": p.question_count
    } for p in pools]


# ── ENDPOINT 2: GET /interview/pool/{pool_id} ────────────────────────
@router.get("/pool/{pool_id}", response_model=QuestionPoolResponse)
async def get_pool(
    pool_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the question pool by ID."""
    pool = db.query(ApprovedQuestionPool).filter(
        ApprovedQuestionPool.id == pool_id
    ).first()

    if not pool:
        raise HTTPException(status_code=404, detail="Question pool not found")

    owner_id = _assessment_session_owner_id(db, pool.session_id)
    if owner_id != current_user.id and current_user.role not in _STAFF_ROLES:
        raise HTTPException(status_code=404, detail="Question pool not found")

    return QuestionPoolResponse(
        pool_id=pool.id,
        questions=pool.question_pool,
        approved=pool.admin_approved,
        extracted_skills=pool.extracted_skills,
        detected_role=pool.detected_role
    )


@router.post("/advanced-proctoring/analyze-frame")
async def analyze_frame(
    frame: UploadFile = File(...),
    session_id: int = Query(..., description="Interview session id"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate session ownership
    interview = db.query(InterviewSession).filter(InterviewSession.id == session_id).first()
    if not interview:
        raise HTTPException(status_code=400, detail="Invalid session_id")
    # Ensure current_user owns the interview's assessment session or is admin
    owner_id = _assessment_session_owner_id(db, interview.session_id)
    if owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized for this session")

    content = await frame.read()
    detections = detect_phones(content)
    phone_count = len(detections)

    # Log detections as separate violations
    for det in detections:
        await log_violation(db, session_id, event_type="phone_detected", confidence_score=det.get("confidence"), face_count=None, metadata={"bbox": det.get("bbox")})

    return {"violations": detections, "phone_count": phone_count}


@router.post("/advanced-proctoring/log-event")
async def log_event(
    req: LogEventRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify session ownership
    interview = db.query(InterviewSession).filter(InterviewSession.id == req.session_id).first()
    if not interview:
        raise HTTPException(status_code=400, detail="Invalid session_id")
    owner_id = _assessment_session_owner_id(db, interview.session_id)
    if owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized for this session")

    success = await log_violation(db, req.session_id, req.event_type, req.confidence_score, req.face_count, req.metadata)

    return {"status": "logged" if success else "queued", "event_type": req.event_type}


# ── ENDPOINT 3: PUT /interview/pool/{pool_id}/approve ────────────────
@router.put("/pool/{pool_id}/approve", response_model=ApprovePoolResponse)
async def approve_pool(
    pool_id: int,
    req: ApprovePoolRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve or reject a question pool."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    pool = db.query(ApprovedQuestionPool).filter(
        ApprovedQuestionPool.id == pool_id
    ).first()

    if not pool:
        raise HTTPException(status_code=404, detail="Pool not found")

    pool.admin_approved = req.approved
    if req.approved:
        pool.approved_by = current_user.id
        pool.approved_at = datetime.now()

    db.commit()

    return ApprovePoolResponse(
        status="approved" if req.approved else "rejected"
    )


# ── Active-round interview bootstrap helpers ──────────────────────────
# A Mock Drive can contain more than one interview round (technical + HR),
# both persisted as AssessmentRound(round_type="interview") and sharing one
# AssessmentSession. These helpers resolve which round is active and select the
# matching approved pool so the two rounds never bleed into each other.
_INTERVIEW_ROUND_KEYS = ("technical_interview", "hr_interview")


def _active_interview_round(db: Session, session_id: int):
    """Return the session's currently active interview round, if any."""
    from app.models.assessment import AssessmentRound

    return (
        db.query(AssessmentRound)
        .filter(
            AssessmentRound.session_id == session_id,
            AssessmentRound.round_type == "interview",
            AssessmentRound.status == "active",
        )
        .order_by(AssessmentRound.id.desc())
        .first()
    )


def _canonical_interview_round_key(db: Session, session_id: int, assessment_round) -> str:
    """Resolve the canonical round key ("technical_interview"/"hr_interview").

    Prefers the persisted canonical key (``practice_type``) so a technical and
    an HR interview — which share ``round_type="interview"`` — stay distinct,
    then falls back to the blueprint's active-round resolution, and finally to
    ``technical_interview``.
    """
    stored = getattr(assessment_round, "practice_type", None)
    if stored in _INTERVIEW_ROUND_KEYS:
        return stored
    _, _, round_key = get_session_active_blueprint_round_config(
        db, session_id, "technical_interview"
    )
    if round_key in _INTERVIEW_ROUND_KEYS:
        return round_key
    return "technical_interview"


def _phase_for_interview_round_key(round_key: str) -> str:
    return "HR" if round_key == "hr_interview" else "TECHNICAL"


def _approved_pool_for_phase(
    db: Session, session_id: int, phase: str
) -> Optional[ApprovedQuestionPool]:
    """Return the approved pool that contains questions for ``phase``.

    Selects the pool whose content actually holds questions for this phase so
    two interview rounds on one session never share the wrong questions; falls
    back to the earliest pool for legacy single-pool data.
    """
    pools = (
        db.query(ApprovedQuestionPool)
        .filter(
            ApprovedQuestionPool.session_id == session_id,
            ApprovedQuestionPool.admin_approved == True,
        )
        .order_by(ApprovedQuestionPool.id.asc())
        .all()
    )
    for pool in pools:
        if any((q or {}).get("phase") == phase for q in (pool.question_pool or [])):
            return pool
    return pools[0] if pools else None


def _approved_pool_for_interview(
    db: Session, interview: InterviewSession
) -> Optional[ApprovedQuestionPool]:
    return _approved_pool_for_phase(db, interview.session_id, interview.phase)


def _ensure_interview_pool(
    db: Session, session_id: int, round_key: str, phase: str
) -> ApprovedQuestionPool:
    """Return an approved pool for the round, creating one if needed.

    For blueprint-backed sessions this clones the pre-generated, validated pool
    (no candidate-time LLM call). ``round_key`` is the canonical Mock Drive key
    so the correct technical/HR pool is cloned.
    """
    approved_pool = _approved_pool_for_phase(db, session_id, phase)
    if approved_pool is not None:
        return approved_pool

    questions, _, _ = _generate_question_pool_for_session(
        db, session_id, [], {}, round_key
    )
    approved_pool = ApprovedQuestionPool(
        session_id=session_id,
        extracted_skills=[],
        extracted_projects={},
        question_pool=questions,
        admin_approved=True,
        approved_by=None,
        approved_at=datetime.now(),
        detected_role=None,
    )
    db.add(approved_pool)
    db.commit()
    db.refresh(approved_pool)
    return approved_pool


# ── ENDPOINT 4: POST /interview/session/start ──────────────────────────
@router.post("/session/start", response_model=StartInterviewResponse)
async def start_interview(
    pool_id: int = Query(..., description="Question pool ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a new interview session using an approved question pool."""

    approved_pool = db.query(ApprovedQuestionPool).filter(
        ApprovedQuestionPool.id == pool_id,
        ApprovedQuestionPool.admin_approved == True,
    ).first()

    if not approved_pool:
        raise HTTPException(
            status_code=400,
            detail="Question pool not found or not approved.",
        )

    session_id = approved_pool.session_id
    if _assessment_session_owner_id(db, session_id) != current_user.id:
        raise HTTPException(
            status_code=404,
            detail="Question pool not found or not approved.",
        )

    first_q = approved_pool.question_pool[0] if (approved_pool.question_pool and len(approved_pool.question_pool) > 0) else {}
    interview_phase = first_q.get("phase", "HR").upper()
    fallback_round = "hr_interview" if interview_phase == "HR" else "technical_interview"
    snapshot, round_config, _ = get_session_active_blueprint_round_config(
        db, session_id, fallback_round
    )
    total_turns = 10
    if snapshot and round_config:
        configured_count = configured_question_count(round_config)
        if configured_count is not None:
            if len(approved_pool.question_pool) < configured_count:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"This interview pool has {len(approved_pool.question_pool)} questions, "
                        f"but the approved blueprint requires {configured_count}. Regenerate the pool."
                    ),
                )
            total_turns = configured_count

    rl_engine = InterviewRLEngine()
    initial_state = rl_engine.to_dict()
    initial_state["interview_type"] = interview_phase.lower()

    interview = InterviewSession(
        session_id=session_id,
        phase=interview_phase,
        current_turn=0,
        total_turns=total_turns,
        rl_state=initial_state,
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)

    assessment_session = (
        db.query(AssessmentSession)
        .filter(AssessmentSession.id == session_id)
        .first()
    )
    active_round = _active_interview_round(db, session_id)

    return StartInterviewResponse(
        interview_id=interview.id,
        phase=interview_phase,
        total_turns=total_turns,
        round_expires_at=active_round.expires_at if active_round else None,
        session_expires_at=(
            assessment_session.expires_at if assessment_session else None
        ),
    )


# ── ENDPOINT 4b: POST /interview/session/start-active ──────────────────
@router.post("/session/start-active", response_model=StartInterviewResponse)
async def start_active_interview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Idempotently start or resume the interview for the caller's active round.

    ``POST /session/start`` requires a ``pool_id`` and always creates a new
    interview session. Navigating to the interview screen — e.g. resuming a
    Mock Drive or refreshing the page — has no pool id and must be safe to
    repeat, so this endpoint resolves the caller's active interview round,
    guarantees an approved question pool exists for it (cloning the
    pre-generated blueprint pool when available — no candidate-time LLM call),
    and returns the existing active interview session instead of creating a
    second one.
    """
    session = (
        db.query(AssessmentSession)
        .filter(
            AssessmentSession.user_id == current_user.id,
            AssessmentSession.status == "in_progress",
        )
        .order_by(AssessmentSession.id.desc())
        .first()
    )
    if session is None:
        raise HTTPException(status_code=404, detail="No active assessment session")

    # Scoped to Mock Drive: the standalone/practice interview is bootstrapped by
    # the resume-upload flow (which sets localStorage.interview_id). Only the
    # Mock Drive interview round navigates straight to /interview without it.
    from app.models.assessment_context import AssessmentContext

    context = (
        db.query(AssessmentContext)
        .filter(AssessmentContext.id == session.context_id)
        .first()
    )
    if context is None or context.mode != "mock_drive":
        raise HTTPException(
            status_code=404, detail="No active mock drive interview round"
        )

    assessment_round = _active_interview_round(db, session.id)
    if assessment_round is None:
        raise HTTPException(
            status_code=404, detail="No active interview round for this session"
        )

    round_key = _canonical_interview_round_key(db, session.id, assessment_round)
    phase = _phase_for_interview_round_key(round_key)

    # Resume an existing active interview for this exact round before creating
    # one (matched by phase so a finished/abandoned technical interview is never
    # resumed as the HR interview, since both share one session).
    existing = (
        db.query(InterviewSession)
        .filter(
            InterviewSession.session_id == session.id,
            InterviewSession.phase == phase,
            InterviewSession.status == "ACTIVE",
        )
        .order_by(InterviewSession.id.desc())
        .first()
    )
    if existing is not None:
        return StartInterviewResponse(
            interview_id=existing.id,
            phase=existing.phase,
            total_turns=existing.total_turns,
            round_expires_at=assessment_round.expires_at,
            session_expires_at=session.expires_at,
        )

    approved_pool = _ensure_interview_pool(db, session.id, round_key, phase)

    _, round_config, _ = get_session_active_blueprint_round_config(
        db, session.id, round_key
    )
    total_turns = configured_question_count(round_config)
    if not total_turns:
        total_turns = len(approved_pool.question_pool or []) or 10

    rl_engine = InterviewRLEngine()
    initial_state = rl_engine.to_dict()
    initial_state["interview_type"] = phase.lower()

    interview = InterviewSession(
        session_id=session.id,
        phase=phase,
        current_turn=0,
        total_turns=total_turns,
        rl_state=initial_state,
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)

    return StartInterviewResponse(
        interview_id=interview.id,
        phase=phase,
        total_turns=total_turns,
        round_expires_at=assessment_round.expires_at,
        session_expires_at=session.expires_at,
    )


# ── ENDPOINT 5: GET /interview/session/{interview_id}/next ─────────────
@router.get("/session/{interview_id}/next", response_model=NextQuestionResponse)
async def get_next_question(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get the next interview question.

    Called ONLY for initial load (turn 0). After that, /respond
    returns next question data in its response.
    """

    # Fetch interview session (owner only — this call mutates interview state)
    interview = _get_interview_for_user(
        db, interview_id, current_user, allow_staff=False
    )

    # A completed interview is a terminal state, so short-circuit BEFORE the
    # expiry check (mirroring /complete's idempotent return). `status` is the
    # authoritative signal: early user-submitted completion sets
    # status="COMPLETED" without advancing `phase`, so checking phase alone lets
    # a finished attempt slip past this guard and surface as a misleading 410
    # once its deadlines have also elapsed.
    if interview.status == "COMPLETED" or interview.phase == "COMPLETE":
        raise HTTPException(status_code=400, detail="Interview already completed")

    _require_interview_not_expired(db, interview)

    # Fetch the approved pool for this interview's phase (a session can hold
    # both a technical and an HR interview round, each with its own pool)
    approved_pool = _approved_pool_for_interview(db, interview)

    if not approved_pool:
        raise HTTPException(status_code=404, detail="No approved question pool")

    # Restore RL engine
    rl_engine = InterviewRLEngine()
    rl_engine.from_dict(interview.rl_state or {})

    # Build current state for RL
    state = {
        "last_score": 0.5,
        "turn": interview.current_turn,
    }

    # Get last score if available
    last_turn = db.query(InterviewTurn).filter(
        InterviewTurn.interview_id == interview_id
    ).order_by(InterviewTurn.turn_number.desc()).first()

    if last_turn and last_turn.final_score is not None:
        state["last_score"] = last_turn.final_score

    # Select difficulty using RL
    difficulty = rl_engine.select_difficulty(state)

    # Question selection (strict uniqueness)
    pool = approved_pool.question_pool
    asked_ids = set(rl_engine.asked_question_ids)

    # Step a: Filter out already-asked questions
    available = [q for q in pool if q.get("id") not in asked_ids]

    # Step b: Filter by phase
    phase_filtered = [q for q in available if q.get("phase") == interview.phase]

    # Step c: Filter by RL-selected difficulty
    diff_filtered = [q for q in phase_filtered if q.get("difficulty") == difficulty]

    # Step d: Relax difficulty if needed
    if diff_filtered:
        selected = diff_filtered[0]
    elif phase_filtered:
        selected = phase_filtered[0]
    elif available:
        selected = available[0]
    else:
        # Step f: All exhausted — use full pool
        logger.warning("Question pool exhausted, reusing questions")
        selected = pool[0] if pool else None
        if not selected:
            raise HTTPException(status_code=400, detail="No questions available")

    question_text = selected["question"]
    question_id = selected.get("id", hashlib.md5(question_text.encode()).hexdigest()[:8])

    # CRITICAL: Check if this question was already asked
    if question_id in asked_ids:
        logger.warning(f"Question {question_id} was already asked! This should not happen.")
        # Try to find a different question
        for q in available:
            alt_id = q.get("id", hashlib.md5(q["question"].encode()).hexdigest()[:8])
            if alt_id not in asked_ids:
                selected = q
                question_text = selected["question"]
                question_id = alt_id
                logger.info(f"Switched to alternative question {question_id}")
                break

    logger.info(f"Selected question {question_id}: {question_text[:50]}... (asked_ids: {len(asked_ids)})")

    # Save question to rl_state (question ownership)
    rl_engine.current_question_text = question_text
    rl_engine.current_question_difficulty = selected.get("difficulty", difficulty)
    rl_engine.current_question_id = question_id
    rl_engine.asked_question_ids.append(question_id)

    # DO NOT reset turn counters here — counters reset in /respond only
    interview.rl_state = rl_engine.to_dict()
    db.commit()

    # Rephrase using Groq (with Redis cache)
    # Blueprint-pool questions are already role-specific and pre-validated, so
    # they are served verbatim: no LLM round-trip at candidate time.
    cache_key = f"question:{hashlib.md5(question_text.encode()).hexdigest()}:{difficulty}"
    rephrased = None

    if not selected.get("blueprint_pool"):
        redis_cache = _get_redis_client()
        if redis_cache:
            try:
                cached = redis_cache.get(cache_key)
                if isinstance(cached, (bytes, bytearray)):
                    rephrased = cached.decode()
                elif isinstance(cached, str):
                    rephrased = cached
            except Exception as e:
                logger.warning(f"Redis get failed: {str(e)}")

        if not rephrased:
            rephrased = groq_service.rephrase_question(question_text, difficulty)
            if redis_cache:
                try:
                    redis_cache.setex(cache_key, 86400, rephrased)
                except Exception as e:
                    logger.warning(f"Redis set failed: {str(e)}")
    if not rephrased:
        rephrased = question_text

    return NextQuestionResponse(
        turn_number=interview.current_turn + 1,
        question=rephrased,
        question_id=question_id,
        difficulty=selected.get("difficulty", difficulty),
        phase=interview.phase,
    )


# ══════════════════════════════════════════════════════════════════════════
# ENDPOINT 6: POST /interview/session/{interview_id}/respond
# 10-STEP DETERMINISTIC PIPELINE
# ══════════════════════════════════════════════════════════════════════════
@router.post("/session/{interview_id}/respond", response_model=SubmitResponseResponse)
async def submit_response(
    interview_id: int,
    req: SubmitResponseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit interview response — 10-step deterministic pipeline.

    1. Load state  2. Silence check  3. Classify  4. Behavior score
    5. Final score  6. Decision engine  7. Pre-fetch  8. Brain
    9. RL update  10. Persist + return
    """

    # ── STEP 0: Load state ──────────────────────────────────────────────
    # Owner only — submitting answers must never be possible for another
    # candidate's interview.
    interview = _get_interview_for_user(
        db, interview_id, current_user, allow_staff=False
    )

    _require_interview_not_expired(db, interview)

    rl_state = dict(interview.rl_state or {})

    rl_engine = InterviewRLEngine()
    rl_engine.from_dict(rl_state)

    # Question from rl_state — NEVER from request body
    question = rl_state.get("current_question_text", "")
    difficulty = rl_state.get("current_question_difficulty", "MEDIUM")

    if not question:
        raise HTTPException(status_code=400, detail="No active question found")

    transcript = (req.transcript or "").strip()

    # ── STEP 1: Silence check ───────────────────────────────────────────
    force_next = False

    if not transcript or len(transcript) < 5:
        if rl_state.get("silence_count", 0) == 0:
            rl_state["silence_count"] = 1
            interview.rl_state = rl_state
            db.commit()

            return SubmitResponseResponse(
                action="RETRY",
                message="I didn't catch that. Could you please repeat your answer?",
                is_complete=False,
                scores=None,
                next_question=None,
            )
        else:
            # Second silence — force move on with 0 score
            content_score = 0.0
            intent = "NEUTRAL"
            quality = "SHORT"
            missing_part = None
            force_next = True
    else:
        content_score = 0.0
        intent = "NEUTRAL"
        quality = "SHORT"
        missing_part = None

    # ── STEP 2: Classifier (skip if force_next) ─────────────────────────
    if not force_next:
        classifier_result = groq_service.classify_answer(
            question,
            transcript,
            interview_type=rl_state.get("interview_type", "technical"),
        )
        quality = classifier_result["quality"]
        intent = classifier_result["intent"]
        missing_part = classifier_result.get("missing_part")
        content_score = classifier_result["content_score"]

    # ── STEP 3: Behavior scoring ────────────────────────────────────────
    snapshot = {}
    if req.behavioral_snapshot:
        snapshot = req.behavioral_snapshot.model_dump()

    response_time_sec = req.response_time_sec or 0.0

    eye_contact = snapshot.get("eye_contact_pct", 0.5)
    head_stability = snapshot.get("head_stability", 0.5)

    if response_time_sec > 5:
        voice_score = 1.0
    elif response_time_sec > 2:
        voice_score = 0.5
    else:
        voice_score = 0.0

    behavior_score = (
        0.4 * eye_contact +
        0.3 * voice_score +
        0.3 * head_stability
    )

    # ── STEP 4: Final score ─────────────────────────────────────────────
    intent_score_map = {
        "POSITIVE": 1.0,
        "NEUTRAL": 0.6,
        "NEGATIVE": 0.3,
    }
    intent_score = intent_score_map.get(intent, 0.6)

    final_score = (
        0.5 * content_score +
        0.3 * intent_score +
        0.2 * behavior_score
    )

    # ── STEP 5: Decision engine ─────────────────────────────────────────
    followup_type = None
    action = "NEXT"  # default

    if force_next:
        action = "NEXT"

    elif rl_state.get("followup_count", 0) >= 2:
        # Hard cap — ALWAYS checked first
        action = "NEXT"

    elif intent == "NEGATIVE":
        if rl_state.get("negative_count", 0) == 0:
            rl_state["negative_count"] = rl_state.get("negative_count", 0) + 1
            rl_state["followup_count"] = rl_state.get("followup_count", 0) + 1
            action = "FOLLOWUP"
            followup_type = "NEGATIVE"
        else:
            action = "NEXT"

    elif quality == "IRRELEVANT":
        if rl_state.get("irrelevant_count", 0) == 0:
            rl_state["irrelevant_count"] = rl_state.get("irrelevant_count", 0) + 1
            rl_state["followup_count"] = rl_state.get("followup_count", 0) + 1
            action = "FOLLOWUP"
            followup_type = "IRRELEVANT"
        else:
            action = "NEXT"

    elif quality == "SHORT":
        rl_state["followup_count"] = rl_state.get("followup_count", 0) + 1
        action = "FOLLOWUP"
        followup_type = "SHORT"

    elif quality == "PARTIAL":
        rl_state["followup_count"] = rl_state.get("followup_count", 0) + 1
        action = "FOLLOWUP"
        followup_type = "PARTIAL"

    elif quality == "GOOD":
        action = "NEXT"

    # Turn advancement check
    if action == "NEXT":
        if interview.current_turn + 1 >= interview.total_turns:
            action = "COMPLETE"
        else:
            interview.current_turn += 1
            # Reset turn counters
            rl_state["followup_count"] = 0
            rl_state["irrelevant_count"] = 0
            rl_state["negative_count"] = 0
            rl_state["silence_count"] = 0

    # ── STEP 6: Pre-fetch next question ─────────────────────────────────
    next_question_obj = None

    if action == "NEXT":
        # Phase-aware pool selection (technical vs HR may share a session)
        approved_pool = _approved_pool_for_interview(db, interview)

        if approved_pool:
            pool = approved_pool.question_pool
            all_asked = set(rl_state.get("asked_question_ids", []))

            available = [q for q in pool if q.get("id") not in all_asked]
            if not available:
                available = pool  # All exhausted — reuse

            # Determine phase for next question
            next_phase = "TECHNICAL" if interview.current_turn >= 5 else interview.phase

            # Filter by phase then difficulty
            next_rl_state = {
                "last_score": final_score,
                "turn": interview.current_turn,
            }
            next_difficulty = rl_engine.select_difficulty(next_rl_state)

            phase_filtered = [q for q in available if q.get("phase") == next_phase]
            diff_filtered = [q for q in phase_filtered if q.get("difficulty") == next_difficulty]

            if diff_filtered:
                next_question_obj = diff_filtered[0]
            elif phase_filtered:
                next_question_obj = phase_filtered[0]
            elif available:
                next_question_obj = available[0]
            else:
                next_question_obj = pool[0] if pool else None

    # ── STEP 7: Interviewer Brain ───────────────────────────────────────
    brain_response = groq_service.generate_interviewer_response(
        question=question,
        answer=transcript,
        quality=quality,
        intent=intent,
        missing_part=missing_part,
        action=action,
        followup_type=followup_type,
        next_question=next_question_obj["question"] if next_question_obj else None,
        conversation_history=rl_state.get("conversation_history", []),
    )

    # ── STEP 8: RL reward update ────────────────────────────────────────
    reward = None
    if action in ("NEXT", "COMPLETE"):
        reward = rl_engine.compute_reward(
            final_score=final_score,
            quality=quality,
            intent=intent,
            difficulty=difficulty,
            content_score=content_score,
        )
        current_state = {
            "last_score": rl_state.get("last_score", 0.5),
            "turn": interview.current_turn - 1 if action == "NEXT" else interview.current_turn,
        }
        next_rl_state_for_update = {
            "last_score": final_score,
            "turn": interview.current_turn,
        }
        rl_engine.update(current_state, difficulty, reward, next_rl_state_for_update)
        rl_state["last_score"] = final_score

    # ── STEP 9: Persist state ───────────────────────────────────────────

    # Update conversation history
    conv_hist = rl_state.get("conversation_history", [])
    conv_hist.append({"role": "interviewer", "content": question})
    conv_hist.append({"role": "candidate", "content": transcript})
    rl_state["conversation_history"] = conv_hist[-6:]  # Cap at 6

    # Save next question to rl_state ONLY here (not in pre-fetch)
    if action == "NEXT" and next_question_obj:
        rl_state["current_question_text"] = next_question_obj["question"]
        rl_state["current_question_difficulty"] = next_question_obj.get("difficulty", "MEDIUM")
        rl_state["current_question_id"] = next_question_obj.get("id")
        asked_ids = rl_state.get("asked_question_ids", [])
        asked_ids.append(next_question_obj.get("id"))
        rl_state["asked_question_ids"] = asked_ids

    # Phase transition
    if interview.current_turn == 5:
        interview.phase = "TECHNICAL"

    if action == "COMPLETE":
        interview.phase = "COMPLETE"

    # Serialize RL engine back to rl_state
    rl_dict = rl_engine.to_dict()
    rl_state["q_table"] = rl_dict["q_table"]
    rl_state["epsilon"] = rl_dict["epsilon"]
    interview.rl_state = rl_state

    # Get parent_turn_id for followup rows
    parent_turn_id = None
    if action == "FOLLOWUP":
        last_main_turn = db.query(InterviewTurn).filter(
            InterviewTurn.interview_id == interview.id,
            InterviewTurn.is_followup == False,
        ).order_by(InterviewTurn.id.desc()).first()
        parent_turn_id = last_main_turn.id if last_main_turn else None

    # Save InterviewTurn row
    turn = InterviewTurn(
        interview_id=interview.id,
        turn_number=interview.current_turn,
        question_text=question,
        question_difficulty=difficulty,
        candidate_response=transcript,
        response_time_sec=response_time_sec,
        content_score=content_score,
        final_score=final_score,
        intent=intent,
        behavioral_snapshot=snapshot,
        rl_reward=reward,
        is_followup=(action == "FOLLOWUP"),
        followup_number=rl_state.get("followup_count", 0),
        parent_turn_id=parent_turn_id,
    )
    db.add(turn)
    db.commit()

    # ── STEP 10: Return response ────────────────────────────────────────
    scores = ScoresInfo(
        content_score=content_score,
        intent_score=intent_score,
        behavior_score=behavior_score,
        final_score=final_score,
    )

    next_q_info = None
    if action == "NEXT" and next_question_obj:
        next_q_info = NextQuestionInfo(
            text=next_question_obj["question"],
            difficulty=next_question_obj.get("difficulty", "MEDIUM"),
            phase=interview.phase,
            turn_number=interview.current_turn,
        )

    summary = None
    if action == "COMPLETE":
        all_main_turns = db.query(InterviewTurn).filter(
            InterviewTurn.interview_id == interview.id,
            InterviewTurn.is_followup == False,
        ).all()
        total_followups = db.query(InterviewTurn).filter(
            InterviewTurn.interview_id == interview.id,
            InterviewTurn.is_followup == True,
        ).count()
        main_scores = [t.final_score for t in all_main_turns if t.final_score is not None]
        avg_score = sum(main_scores) / max(len(main_scores), 1)
        followup_rate = total_followups / max(len(all_main_turns), 1) * 100

        summary = InterviewSummaryInfo(
            total_turns=len(all_main_turns),
            avg_final_score=round(avg_score, 2),
            followup_rate=round(followup_rate, 1),
        )

        # Mark interview as COMPLETED and its AssessmentRound as completed,
        # then advance the Mock Drive if this interview is part of one.
        interview.status = "COMPLETED"
        interview.completion_reason = "ALL_TURNS_COMPLETE"
        interview.completed_at = datetime.now()
        db.commit()

        from app.models.assessment import AssessmentRound as AR, AssessmentSession as AS2
        asmnt_session = (
            db.query(AS2)
            .filter(AS2.user_id == current_user.id, AS2.status == "in_progress")
            .order_by(AS2.id.desc())
            .first()
        )
        if asmnt_session:
            int_round = (
                db.query(AR)
                .filter(
                    AR.session_id == asmnt_session.id,
                    AR.round_type == "interview",
                    AR.status == "active",
                )
                .first()
            )
            if int_round:
                int_round.status = "completed"
                int_round.completed_at = datetime.now()
                db.commit()
            _try_advance_mock_drive(db, asmnt_session.id)

    return SubmitResponseResponse(
        action=action,
        message=brain_response,
        is_complete=(action == "COMPLETE"),
        followup_type=followup_type,
        next_question=next_q_info,
        scores=scores,
        interview_summary=summary,
    )


# ── ENDPOINT 7: POST /interview/stt ────────────────────────────────────
from fastapi.responses import JSONResponse

@router.post("/stt")
async def speech_to_text(
    audio: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Transcribes candidate audio using Groq Whisper API.
    Replaces local Whisper model (was causing 503 errors).

    Accepted formats: webm, wav, mp3, mp4, m4a, ogg, flac
    Max file size: 25MB
    """
    import os
    import tempfile

    # Read audio bytes
    audio_bytes = await audio.read()

    # Validate file size — Groq limit is 25MB
    if len(audio_bytes) > 25 * 1024 * 1024:
        return {"transcript": ""}

    # Validate file is not empty
    if len(audio_bytes) < 100:
        return {"transcript": ""}

    # Determine file extension from upload filename
    # MediaRecorder default is webm — use as fallback
    original_name = audio.filename or "audio.webm"
    extension = os.path.splitext(original_name)[1]
    if not extension or extension not in [
        ".webm", ".wav", ".mp3", ".mp4",
        ".m4a", ".ogg", ".flac", ".mpga", ".mpeg"
    ]:
        extension = ".webm"

    tmp_path = None
    try:
        # Write to temp file with correct extension
        with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        # Transcribe via Groq API
        transcript = groq_service.transcribe_audio(tmp_path)
        return {"transcript": transcript}

    except Exception as e:
        error_str = str(e).lower()

        if "429" in error_str or "rate limit" in error_str:
            # Return 429 so frontend can retry with backoff
            # Do NOT treat as silence — that would penalize
            # the candidate unfairly
            return JSONResponse(
                status_code=429,
                content={"detail": "STT rate limited. Retry shortly."}
            )

        # Any other error — return empty transcript
        # /respond endpoint will handle as silence
        print(f"[STT Endpoint Error] {e}")
        return {"transcript": ""}

    finally:
        # Always delete temp file
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ── ENDPOINT 8: POST /interview/tts ────────────────────────────────────
@router.post("/tts")
async def synthesize_speech(
    text: str = Query(..., max_length=2500, description="Text to synthesize (max 2500 chars)"),
):
    """Synthesize speech using Sarvam.ai Bulbul v3 API."""
    from app.services.sarvam_service import text_to_speech
    from fastapi.responses import Response

    try:
        audio_bytes = await text_to_speech(text)
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except Exception as e:
        error_str = str(e).lower()
        if "rate limit" in error_str:
            raise HTTPException(status_code=429, detail="TTS rate limited. Try again shortly.")
        elif "api key" in error_str:
            raise HTTPException(status_code=503, detail="TTS service configuration error")
        elif "too long" in error_str:
            raise HTTPException(status_code=400, detail="Text too long for TTS (max 2500 chars)")
        else:
            logger.error(f"Sarvam TTS failed: {str(e)}")
            raise HTTPException(status_code=503, detail="TTS temporarily unavailable.")


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINT: GET /interview/session/{interview_id}/status
# Return interview session status, scores, and timing info
# ═══════════════════════════════════════════════════════════════════════════
@router.get("/session/{interview_id}/status")
async def get_interview_status(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return status and score summary for an interview session."""
    interview = _get_interview_for_user(db, interview_id, current_user)

    turns = db.query(InterviewTurn).filter(
        InterviewTurn.interview_id == interview_id,
        InterviewTurn.is_followup == False,
    ).all()
    scores = [t.final_score for t in turns if t.final_score is not None]
    avg_score = round(sum(scores) / max(len(scores), 1), 2) if scores else 0.0

    return {
        "interview_id": interview.id,
        "status": interview.status,
        "phase": interview.phase,
        "total_questions": interview.total_turns,
        "questions_attempted": interview.current_turn,
        "average_score": avg_score,
        "start_time": interview.created_at.isoformat() if interview.created_at else None,
        "end_time": interview.completed_at.isoformat() if interview.completed_at else None,
    }


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINT: POST /interview/session/{interview_id}/complete
# Early interview completion - idempotent
# ═══════════════════════════════════════════════════════════════════════════
@router.post("/session/{interview_id}/complete")
async def complete_interview(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Complete interview session early (user submitted before all questions).

    Idempotent: safe to call multiple times, returns existing completion data.
    """
    interview = _get_interview_for_user(
        db, interview_id, current_user, allow_staff=False
    )

    # Idempotent: if already completed, return existing computed values
    if interview.status == "COMPLETED":
        turns = db.query(InterviewTurn).filter(
            InterviewTurn.interview_id == interview_id,
            InterviewTurn.is_followup == False
        ).all()
        scores = [t.final_score for t in turns if t.final_score is not None]
        return {
            "status": "COMPLETED",
            "completion_reason": interview.completion_reason,
            "questions_attempted": len(turns),
            "questions_total": interview.total_turns,
            "performance_score": round(sum(scores) / max(len(scores), 1), 2),
            "completion_ratio": round(len(turns) / max(interview.total_turns, 1), 2),
        }

    # Expiration: an expired attempt must not be completed/finalized (which
    # would also advance the Mock Drive) after its persisted deadline passed.
    _require_interview_not_expired(db, interview)

    # Mark completed
    interview.status = "COMPLETED"
    interview.completion_reason = "USER_SUBMITTED"
    interview.completed_at = datetime.now()
    db.commit()

    # Also complete the AssessmentRound for THIS interview (not done by the
    # engine itself). Scope strictly to the interview's own assessment session
    # so completing an old/other interview can never finalize a different
    # attempt of the same candidate.
    from app.models.assessment import AssessmentRound, AssessmentSession as ASession
    assessment_session = (
        db.query(ASession)
        .filter(
            ASession.id == interview.session_id,
            ASession.status == "in_progress",
        )
        .first()
    )
    mock_drive_result = None
    if assessment_session:
        interview_round = (
            db.query(AssessmentRound)
            .filter(
                AssessmentRound.session_id == assessment_session.id,
                AssessmentRound.round_type == "interview",
                AssessmentRound.status == "active",
            )
            .first()
        )
        if interview_round:
            interview_round.status = "completed"
            interview_round.completed_at = datetime.now()
            db.commit()

        # If this session is part of a Mock Drive, advance/finalize it
        mock_drive_result = _try_advance_mock_drive(db, assessment_session.id)

    turns = db.query(InterviewTurn).filter(
        InterviewTurn.interview_id == interview_id,
        InterviewTurn.is_followup == False
    ).all()
    scores = [t.final_score for t in turns if t.final_score is not None]
    response = {
        "status": "COMPLETED",
        "completion_reason": "USER_SUBMITTED",
        "questions_attempted": len(turns),
        "questions_total": interview.total_turns,
        "performance_score": round(sum(scores) / max(len(scores), 1), 2),
        "completion_ratio": round(len(turns) / max(interview.total_turns, 1), 2),
    }
    if mock_drive_result:
        response["mock_drive"] = mock_drive_result
    return response


# ═══════════════════════════════════════════════════════════════════════════
# ENDPOINT 9: GET /interview/session/{interview_id}/report
# Grouped turns with follow-up rate
# ═══════════════════════════════════════════════════════════════════════════
@router.get("/session/{interview_id}/report", response_model=InterviewReportResponse)
async def get_report(
    interview_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get interview assessment report with grouped turns."""

    interview = _get_interview_for_user(db, interview_id, current_user)

    # Fetch all turns ordered by creation
    all_turns = db.query(InterviewTurn).filter(
        InterviewTurn.interview_id == interview_id
    ).order_by(InterviewTurn.id).all()

    # Separate main and followup turns
    main_turns = [t for t in all_turns if not t.is_followup]
    followup_turns = [t for t in all_turns if t.is_followup]

    # Group follow-ups under their parent
    turn_reviews = []
    for mt in main_turns:
        followups_for_turn = [
            FollowupItem(
                followup_number=f.followup_number,
                question_text=f.question_text,
                candidate_response=f.candidate_response,
                content_score=f.content_score,
                intent=f.intent,
                response_time_sec=f.response_time_sec,
            )
            for f in followup_turns
            if f.parent_turn_id == mt.id
        ]

        # Compute behavior_score from snapshot
        snap = mt.behavioral_snapshot or {}
        eye_contact = snap.get("eye_contact_pct", 0.5)
        head_stability = snap.get("head_stability", 0.5)

        turn_reviews.append(TurnReviewItem(
            turn_number=mt.turn_number,
            question_text=mt.question_text,
            difficulty=mt.question_difficulty,
            candidate_response=mt.candidate_response,
            content_score=mt.content_score,
            intent=mt.intent,
            behavior_score=round(0.5 * eye_contact + 0.5 * head_stability, 2),
            final_score=mt.final_score,
            response_time_sec=mt.response_time_sec,
            rl_reward=mt.rl_reward,
            followups=followups_for_turn,
        ))

    # Compute aggregate metrics
    content_scores = [t.content_score for t in main_turns if t.content_score is not None]
    final_scores = [t.final_score for t in main_turns if t.final_score is not None]

    avg_content = sum(content_scores) / max(len(content_scores), 1)
    avg_final = sum(final_scores) / max(len(final_scores), 1)

    # Behavior score avg
    behavior_scores = []
    for t in all_turns:
        snap = t.behavioral_snapshot or {}
        ec = snap.get("eye_contact_pct", 0.5)
        hs = snap.get("head_stability", 0.5)
        behavior_scores.append(0.5 * ec + 0.5 * hs)
    avg_behavior = sum(behavior_scores) / max(len(behavior_scores), 1)

    # Overall score
    overall_score = avg_final

    # Follow-up rate
    total_followups = len(followup_turns)
    total_main = max(len(main_turns), 1)
    followup_rate = total_followups / total_main * 100

    # Follow-up interpretation
    if followup_rate < 30:
        followup_interp = "Strong candidate, clear communicator"
    elif followup_rate <= 60:
        followup_interp = "Some answers needed prompting"
    else:
        followup_interp = "Candidate struggled to elaborate independently"

    # Generate feedback
    turns_data = [
        {
            "question": t.question_text,
            "answer": (t.candidate_response or "")[:200],
            "score": t.final_score or 0.5,
        }
        for t in main_turns
    ]
    feedback = groq_service.generate_feedback_summary(turns_data)

    # Compute intent_score average
    intent_scores = [t.intent for t in main_turns if t.intent]
    intent_map = {"positive": 1.0, "neutral": 0.6, "negative": 0.2}
    avg_intent = sum(intent_map.get(i, 0.6) for i in intent_scores) / max(len(intent_scores), 1) if intent_scores else None

    # Compute completion_ratio and get completion_reason
    completion_ratio = len(main_turns) / max(interview.total_turns, 1)
    completion_reason = interview.completion_reason

    return InterviewReportResponse(
        overall_score=round(overall_score, 2),
        content_score=round(avg_content, 2),
        behavior_score=round(avg_behavior, 2),
        final_score=round(avg_final, 2),
        intent_score=round(avg_intent, 2) if avg_intent is not None else None,
        completion_ratio=round(completion_ratio, 2),
        completion_reason=completion_reason,
        feedback_summary=feedback,
        turn_reviews=turn_reviews,
        total_turns=len(main_turns),
        followup_rate=round(followup_rate, 1),
        followup_interpretation=followup_interp,
    )


# ═══════════════════════════════════════════════════════════════════════
# ENDPOINT 10: Real-Time Feedback
# ═══════════════════════════════════════════════════════════════════════
@router.post("/realtime-feedback", response_model=RealtimeFeedbackResponse)
async def realtime_feedback(
    snapshot: RealtimeFeedbackRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Returns real-time coaching tips based on behavioral metrics.

    Called by frontend polling (every 3 seconds) during interview recording.
    Provides actionable feedback to improve candidate presentation.
    """
    # Face not detected - highest priority
    if not snapshot.face_detected:
        return RealtimeFeedbackResponse(tip="Ensure your face is visible in the camera.")

    # Poor eye contact
    if snapshot.eye_contact_pct < 0.4:
        return RealtimeFeedbackResponse(tip="Try to maintain eye contact with the camera.")

    # Excessive head movement / instability
    if snapshot.head_stability < 0.4:
        return RealtimeFeedbackResponse(tip="Try to keep your head steady while speaking.")

    # Looking away too often
    if snapshot.looking_away_count > 5:
        return RealtimeFeedbackResponse(tip="Focus on the camera to show engagement.")

    # Moderate eye contact - gentle nudge
    if snapshot.eye_contact_pct < 0.6:
        return RealtimeFeedbackResponse(tip="Good! A bit more eye contact would help.")

    # All good
    return RealtimeFeedbackResponse(tip="Great engagement! Keep it up.")
