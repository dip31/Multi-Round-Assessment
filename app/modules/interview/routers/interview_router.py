"""
Interview Round Router

Handles all HTTP endpoints related to the Interview Round.

Endpoints:
- POST /interview/resume/upload - Upload resume and generate question pool
- GET /interview/pool/{pool_id} - Get approved question pool
- PUT /interview/pool/{pool_id}/approve - Approve/reject question pool
- POST /interview/session/start - Start interview session
- GET /interview/session/{interview_id}/next - Get next question (initial load only)
- POST /interview/session/{interview_id}/respond - Submit response (delegates to InterviewOrchestrator)
- POST /interview/stt - Speech-to-text
- POST /interview/tts - Text-to-speech
- GET /interview/session/{interview_id}/report - Get interview report
- WS /interview/retell/llm/{call_id} - Custom LLM WebSocket for Retell integration

Routes here stay thin: they resolve and authorise the session, then delegate.
The per-turn interview pipeline lives in
``app.modules.interview.services.interview_orchestrator``; question selection
lives in ``question_planner``; the follow-up rules live in ``followup_policy``.
"""

import hashlib
import json
import logging
import tempfile
from datetime import datetime
from typing import Literal, Optional

import redis
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
)
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from sqlalchemy import select

from app.config.settings import settings
from app.core.auth import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.models.profile import UserResume
from app.models.interview import (
    InterviewSession,
    ApprovedQuestionPool,
    InterviewTurn,
    DynamicInterviewer,
)
from app.models.assessment import AssessmentRound
from app.models.assessment import AssessmentSession
from app.services.resume_service import parse_resume
from app.services.groq_service import GroqService
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
    InterviewerListResponse,
    InterviewerProfileResponse,
    InterviewerVoiceInfo,
)
from app.modules.interview.config import interviewer_profiles
from app.modules.interview.services import question_planner
from app.modules.interview.services.interview_orchestrator import (
    InterviewError,
    InterviewOrchestrator,
)
from app.modules.interview.services.interview_rl_engine import InterviewRLEngine
from app.modules.interview.services.retell_adapter import get_retell_adapter, RetellCallConfig
from app.modules.interview.services.retell_llm_websocket import retell_llm_websocket_endpoint
from app.services.phone_detection_service import detect_phones
from app.services.proctoring_logger import log_violation
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/interview",
    tags=["Interview Round"],
)

# ── Retell Custom LLM WebSocket Endpoint ──────────────────────────────────
@router.websocket("/retell/llm/{call_id}")
async def retell_llm_websocket(
    websocket: WebSocket,
    call_id: str,
    adapter = Depends(get_retell_adapter),
):
    """Custom LLM WebSocket for Retell real-time voice integration."""
    await retell_llm_websocket_endpoint(websocket, call_id, adapter)


class LogEventRequest(BaseModel):
    session_id: int
    event_type: str
    confidence_score: float | None = None
    face_count: int | None = None
    metadata: dict | None = None


class RetellTranscriptRequest(BaseModel):
    transcript: str


# Global instances (will be set by app lifespan)
ml_models = {}  # To be populated by app/main.py
groq_service = GroqService(settings.GROQ_API_KEY)

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

    content = None
    try:
        content = await file.read()
        extracted = parse_resume(content)
        pool = groq_service.generate_question_pool(
            extracted["skills"],
            extracted["projects"],
            count=12,
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

    skills = resume.parsed_skills if isinstance(resume.parsed_skills, list) else []
    projects = resume.parsed_projects if isinstance(resume.parsed_projects, list) else []

    pool = groq_service.generate_question_pool(
        skills,
        projects,
        count=12,
        interview_type=interview_type or "technical",
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
    # Ensure current_user owns the session or is admin
    if interview.session_id != current_user.id and current_user.role != "admin":
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
    if interview.session_id != current_user.id and current_user.role != "admin":
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


# ── ENDPOINT 3.5: GET /interview/interviewers ──────────────────────────
@router.get("/interviewers", response_model=InterviewerListResponse)
async def list_interviewers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the interviewers a candidate can choose from.

    Includes both static interviewers (from config) and dynamic interviewers
    (created by admins and stored in database with Retell integration).

    Choosing an interviewer changes the name, face, voice and tone of the
    interview. It does not change the questions, the scoring, or how long the
    interview runs.
    """
    # Get static interviewers from config
    static_profiles = interviewer_profiles.list_interviewers()
    
    # Get dynamic interviewers from database (active only)
    dynamic_interviewers = db.execute(
        select(DynamicInterviewer).where(DynamicInterviewer.is_active == True)
    ).scalars().all()
    
    all_interviewers = []
    
    # Add static interviewers
    for p in static_profiles:
        all_interviewers.append(InterviewerProfileResponse(
            id=p.id,
            name=p.name,
            title=p.title,
            tagline=p.tagline,
            avatar_initials=p.avatar_initials,
            accent=p.accent,
            voice=InterviewerVoiceInfo(
                speaker=p.voice.speaker,
                language_code=p.voice.language_code,
            ),
            greeting=p.render_greeting(),
            is_default=(p.id == interviewer_profiles.DEFAULT_INTERVIEWER_ID),
            is_dynamic=False,
        ))
    
    # Add dynamic interviewers
    for di in dynamic_interviewers:
        all_interviewers.append(InterviewerProfileResponse(
            id=di.slug,
            name=di.name,
            title=di.title,
            tagline=di.tagline,
            avatar_initials=di.avatar_initials,
            accent=di.accent,
            voice=InterviewerVoiceInfo(
                speaker=di.voice_id,
                language_code=di.language_code,
            ),
            greeting=di.greeting,
            is_default=False,
            is_dynamic=True,
        ))
    
    return InterviewerListResponse(
        interviewers=all_interviewers,
        default_interviewer_id=interviewer_profiles.DEFAULT_INTERVIEWER_ID,
    )


@router.get("/voice-modes")
async def get_voice_modes(current_user: User = Depends(get_current_user)):
    """Report which Retell interview modes can be started with current settings."""
    retell_ready = bool(settings.RETELL_API_KEY and settings.RETELL_AGENT_ID)
    return {
        "retell_hosted": {
            "available": retell_ready,
            "reason": None if retell_ready else "Configure RETELL_API_KEY and RETELL_AGENT_ID.",
        },
        "edi5_core": {
            "available": retell_ready and bool(settings.RETELL_LLM_WEBSOCKET_URL),
            "reason": (
                None
                if retell_ready and settings.RETELL_LLM_WEBSOCKET_URL
                else "EDI5 Core requires Retell credentials and RETELL_LLM_WEBSOCKET_URL."
            ),
        },
    }


# ── ENDPOINT 4: POST /interview/session/start ──────────────────────────
@router.post("/session/start", response_model=StartInterviewResponse)
async def start_interview(
    pool_id: int = Query(..., description="Question pool ID"),
    interviewer_id: Optional[str] = Query(
        None,
        description="Selected interviewer persona. Omit to use the default.",
    ),
    voice_mode: Optional[Literal["retell_hosted", "edi5_core"]] = Query(
        None,
        description="Retell-hosted LLM or EDI5 Core interview intelligence.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    adapter = Depends(get_retell_adapter),
):
    """Start a new interview session using an approved question pool."""
    
    # An explicit mode selection enables Retell for this interview only.
    use_retell = voice_mode is not None or settings.INTERVIEW_VOICE_PROVIDER == "retell"
    selected_voice_mode = voice_mode or (
        "edi5_core" if settings.INTERVIEW_VOICE_PROVIDER == "retell" else None
    )
    if use_retell and not settings.RETELL_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="Retell voice is enabled but RETELL_API_KEY is not configured.",
        )
    if selected_voice_mode == "edi5_core" and not settings.RETELL_LLM_WEBSOCKET_URL:
        raise HTTPException(
            status_code=503,
            detail="EDI5 Core mode requires RETELL_LLM_WEBSOCKET_URL. Choose Retell-hosted mode or configure the public WebSocket URL.",
        )

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
    active_round = (
        db.query(AssessmentRound)
        .filter(
            AssessmentRound.session_id == session_id,
            AssessmentRound.round_type == "interview",
            AssessmentRound.status == "active",
        )
        .order_by(AssessmentRound.id.desc())
        .first()
    )

    first_q = approved_pool.question_pool[0] if (approved_pool.question_pool and len(approved_pool.question_pool) > 0) else {}
    interview_phase = first_q.get("phase", "HR").upper()

    rl_engine = InterviewRLEngine()
    initial_state = rl_engine.to_dict()
    initial_state["interview_type"] = interview_phase.lower()

    # Resolved, not trusted: an unknown id becomes the default rather than a
    # 400, so a stale frontend build can never block a candidate from starting
    # their interview. The interviewer has no bearing on assessment, so the
    # fallback is harmless. Note this is deliberately NOT written into
    # rl_state — persona must stay out of the Q-learning state.
    resolved_interviewer_id = interviewer_profiles.resolve_selection(interviewer_id)
    
    # Check if interviewer is a dynamic interviewer with its own Retell Agent
    dynamic_interviewer = None
    retell_agent_id_override = None
    if resolved_interviewer_id:
        dynamic_interviewer = db.execute(
            select(DynamicInterviewer).where(
                DynamicInterviewer.slug == resolved_interviewer_id,
                DynamicInterviewer.is_active == True
            )
        ).scalar_one_or_none()
        if dynamic_interviewer and dynamic_interviewer.retell_agent_id:
            retell_agent_id_override = dynamic_interviewer.retell_agent_id

    # Determine which Retell agent to use: dynamic interviewer's agent or global default
    effective_agent_id = retell_agent_id_override or settings.RETELL_AGENT_ID
    if use_retell and not effective_agent_id:
        raise HTTPException(
            status_code=503,
            detail="Retell voice is enabled but no Retell agent is configured for this interviewer.",
        )

    interview = InterviewSession(
        session_id=session_id,
        round_id=active_round.id if active_round else None,
        phase=interview_phase,
        current_turn=0,
        total_turns=10,
        rl_state=initial_state,
        interviewer_id=resolved_interviewer_id,
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)
    
    # If using Retell, create web call and link it
    retell_call_id = None
    retell_agent_id = None
    retell_access_token = None
    retell_ice_servers = None

    if use_retell:
        try:
            # Build agent override for selected interviewer
            # Note: For retell_hosted, providing a partial retell_llm override crashes Retell.
            # We rely entirely on the Retell Dashboard agent configuration for hosted mode.
            agent_override = None
            if selected_voice_mode != "retell_hosted":
                agent_override = adapter.build_agent_override_for_interviewer(
                    interviewer_id=resolved_interviewer_id,
                    interview_type=interview_phase.lower(),
                )
                if dynamic_interviewer and dynamic_interviewer.greeting:
                    agent_override.setdefault("retell_llm", {})["begin_message"] = dynamic_interviewer.greeting

            # Extract questions for both hosted prompt and dynamic variables
            questions = [
                item.get("question", "").strip()
                for item in (approved_pool.question_pool or [])[:interview.total_turns]
                if isinstance(item, dict) and item.get("question")
            ]

            if selected_voice_mode == "retell_hosted":
                # We don't need to override the general_prompt here anymore.
                # The prompt is configured in the Retell dashboard using {{variables}} 
                # which are populated by the dynamic_variables dict below.
                pass
            
            # Build dynamic variables
            candidate_name = current_user.name or current_user.email.split("@")[0]
            dynamic_variables = adapter.build_dynamic_variables(
                candidate_name=candidate_name,
                interview_type=interview_phase.lower(),
                interviewer_id=resolved_interviewer_id,
                edi5_session_id=interview.id,
                questions=questions,
                detected_role=approved_pool.detected_role,
                total_turns=interview.total_turns,
            )
            
            # Metadata for webhook correlation
            metadata = {
                "edi5_interview_session_id": interview.id,
                "candidate_id": current_user.id,
                "assessment_session_id": session_id,
                "interviewer_id": resolved_interviewer_id,
            }
            
            call_config = RetellCallConfig(
                agent_id=effective_agent_id,
                agent_override=agent_override,
                metadata=metadata,
                dynamic_variables=dynamic_variables,
                llm_websocket_url=(
                    settings.RETELL_LLM_WEBSOCKET_URL
                    if selected_voice_mode == "edi5_core"
                    else None
                ),
            )
            
            web_call = await adapter.create_web_call(call_config)
            
            retell_call_id = web_call.call_id
            retell_agent_id = effective_agent_id
            retell_access_token = web_call.access_token
            retell_ice_servers = web_call.ice_servers
            
            # Update interview session with Retell info
            interview.retell_call_id = retell_call_id
            interview.retell_agent_id = retell_agent_id
            interview.personalization_metadata = {
                **(interview.personalization_metadata or {}),
                "voice_mode": selected_voice_mode or "edi5_core",
            }
            db.commit()
            
            logger.info(f"Created Retell web call {retell_call_id} for EDI5 interview {interview.id} using agent {effective_agent_id}")
            
        except Exception as e:
            logger.exception("Failed to create Retell web call for interview %s", interview.id)
            db.delete(interview)
            db.commit()
            raise HTTPException(
                status_code=502,
                detail="Retell could not start the voice call. Check the Retell configuration and backend logs.",
            ) from e

    return StartInterviewResponse(
        interview_id=interview.id,
        phase=interview_phase,
        total_turns=10,
        interviewer_id=resolved_interviewer_id,
        # Retell-specific fields (added to response for frontend)
        retell_call_id=retell_call_id,
        retell_access_token=retell_access_token,
        retell_ice_servers=retell_ice_servers,
        voice_provider="retell" if use_retell else "legacy",
        voice_mode=selected_voice_mode,
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

    # Fetch interview session
    interview = db.query(InterviewSession).filter(
        InterviewSession.id == interview_id
    ).first()

    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    if interview.phase == "COMPLETE":
        raise HTTPException(status_code=400, detail="Interview already completed")

    # Fetch approved question pool
    approved_pool = db.query(ApprovedQuestionPool).filter(
        ApprovedQuestionPool.session_id == interview.session_id,
        ApprovedQuestionPool.admin_approved == True,
    ).first()

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

    # Question selection (strict uniqueness — no pool reuse on initial load)
    pool = approved_pool.question_pool
    asked_ids = set(rl_engine.asked_question_ids)

    selected = question_planner.select_question(
        pool,
        asked_question_ids=asked_ids,
        phase=interview.phase,
        difficulty=difficulty,
        reuse_exhausted_pool=False,
    )

    if not selected:
        raise HTTPException(status_code=400, detail="No questions available")

    question_text = selected["question"]
    question_id = question_planner.resolve_question_id(selected)

    # CRITICAL: Check if this question was already asked
    if question_id in asked_ids:
        logger.warning(f"Question {question_id} was already asked! This should not happen.")
        alternative = question_planner.find_unasked_alternative(pool, asked_ids)
        if alternative:
            selected = alternative
            question_text = selected["question"]
            question_id = question_planner.resolve_question_id(selected)
            logger.info(f"Switched to alternative question {question_id}")

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
    cache_key = f"question:{hashlib.md5(question_text.encode()).hexdigest()}:{difficulty}"
    rephrased = None

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

    return NextQuestionResponse(
        turn_number=interview.current_turn + 1,
        question=rephrased,
        question_id=question_id,
        difficulty=selected.get("difficulty", difficulty),
        phase=interview.phase,
    )


# ── ENDPOINT 6: POST /interview/session/{interview_id}/respond ─────────
@router.post("/session/{interview_id}/respond", response_model=SubmitResponseResponse)
async def submit_response(
    interview_id: int,
    req: SubmitResponseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit an interview response and get the interviewer's reply.

    The turn pipeline (silence handling, classification, scoring, follow-up
    decision, question pre-fetch, RL update, persistence) lives in
    ``InterviewOrchestrator``. This route only resolves the session and
    translates domain errors into HTTP responses.
    """

    interview = db.query(InterviewSession).filter(
        InterviewSession.id == interview_id
    ).first()

    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    orchestrator = InterviewOrchestrator(db, groq_service)

    try:
        return orchestrator.handle_response(interview, req)
    except InterviewError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)


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
    interviewer_id: Optional[str] = Query(
        None,
        description="Speak in this interviewer's voice. Omit for the default voice.",
    ),
):
    """Synthesize speech using Sarvam.ai Bulbul v3 API.

    SECURITY NOTE (pre-existing, unchanged here): this endpoint has no
    ``get_current_user`` dependency, so it is callable unauthenticated. Adding
    ``interviewer_id`` does not widen that exposure — the parameter only picks
    between a fixed set of voices and an unknown value falls back to the
    default. Flagged rather than fixed because adding auth here would break the
    in-flight audio calls the interview UI makes today; it needs its own change.
    """
    from app.services.sarvam_service import text_to_speech
    from fastapi.responses import Response

    # Resolved server-side from the id. The client never sends a speaker name,
    # so it cannot request an arbitrary voice or drive up cost with exotic
    # parameters.
    voice = interviewer_profiles.get_interviewer(interviewer_id).voice

    try:
        audio_bytes = await text_to_speech(
            text,
            speaker=voice.speaker,
            model=voice.model,
            language_code=voice.language_code,
            pace=voice.pace,
        )
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
    interview = db.query(InterviewSession).filter(InterviewSession.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    turns = db.query(InterviewTurn).filter(
        InterviewTurn.interview_id == interview_id,
        InterviewTurn.is_followup == False,
    ).all()
    scores = [t.final_score for t in turns if t.final_score is not None]
    avg_score = round(sum(scores) / max(len(scores), 1), 2) if scores else 0.0

    return {
        "interview_id": interview.id,
        "session_id": interview.session_id,
        "round_id": interview.round_id,
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
    interview = db.query(InterviewSession).filter(InterviewSession.id == interview_id).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    linked_round = (
        db.query(AssessmentRound)
        .filter(AssessmentRound.id == interview.round_id)
        .first()
        if interview.round_id
        else None
    )

    def finalize_linked_round(scores: list[float]) -> None:
        """Keep the shared assessment lifecycle aligned with interview completion."""
        if linked_round is None or linked_round.status in {"completed", "terminated", "expired"}:
            return
        completed_at = interview.completed_at or datetime.now()
        linked_round.status = "completed"
        linked_round.completed_at = completed_at
        if scores:
            linked_round.score = round(sum(scores) / len(scores), 2)
        from app.services.proctoring_service import stop_proctoring_session
        stop_proctoring_session(db, linked_round.session_id)

    # Idempotent: if already completed, return existing computed values
    if interview.status == "COMPLETED":
        turns = db.query(InterviewTurn).filter(
            InterviewTurn.interview_id == interview_id,
            InterviewTurn.is_followup == False
        ).all()
        scores = [t.final_score for t in turns if t.final_score is not None]
        finalize_linked_round(scores)
        db.commit()
        return {
            "status": "COMPLETED",
            "completion_reason": interview.completion_reason,
            "questions_attempted": len(turns),
            "questions_total": interview.total_turns,
            "performance_score": round(sum(scores) / max(len(scores), 1), 2),
            "completion_ratio": round(len(turns) / max(interview.total_turns, 1), 2),
        }

    # Mark completed
    interview.status = "COMPLETED"
    interview.completion_reason = "USER_SUBMITTED"
    interview.completed_at = datetime.now()
    db.commit()

    turns = db.query(InterviewTurn).filter(
        InterviewTurn.interview_id == interview_id,
        InterviewTurn.is_followup == False
    ).all()
    scores = [t.final_score for t in turns if t.final_score is not None]
    finalize_linked_round(scores)
    db.commit()
    return {
        "status": "COMPLETED",
        "completion_reason": "USER_SUBMITTED",
        "questions_attempted": len(turns),
        "questions_total": interview.total_turns,
        "performance_score": round(sum(scores) / max(len(scores), 1), 2),
        "completion_ratio": round(len(turns) / max(interview.total_turns, 1), 2),
    }


@router.post("/session/{interview_id}/retell-transcript")
async def save_retell_transcript(
    interview_id: int,
    request: RetellTranscriptRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Persist a browser-delivered Retell transcript without requiring webhooks."""
    interview = db.query(InterviewSession).join(
        AssessmentSession,
        AssessmentSession.id == InterviewSession.session_id,
    ).filter(
        InterviewSession.id == interview_id,
        AssessmentSession.user_id == current_user.id,
    ).first()
    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    metadata = dict(interview.personalization_metadata or {})
    metadata["retell_live_transcript"] = request.transcript
    metadata["retell_transcript_source"] = "browser"
    interview.personalization_metadata = metadata
    db.commit()
    return {"status": "saved"}


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

    interview = db.query(InterviewSession).filter(
        InterviewSession.id == interview_id
    ).first()

    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

    metadata = interview.personalization_metadata or {}
    voice_mode = metadata.get("voice_mode")
    hosted_mode = voice_mode == "retell_hosted"

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
    if hosted_mode:
        analysis = metadata.get("retell_analysis") or {}
        feedback = (
            analysis.get("call_summary")
            or "This interview used Retell-hosted interview intelligence. EDI5 per-turn scoring is not enabled for this mode."
        )
    else:
        feedback = groq_service.generate_feedback_summary(turns_data)

    # Compute intent_score average
    intent_scores = [t.intent for t in main_turns if t.intent]
    intent_map = {"positive": 1.0, "neutral": 0.6, "negative": 0.2}
    avg_intent = sum(intent_map.get(i, 0.6) for i in intent_scores) / max(len(intent_scores), 1) if intent_scores else None

    # Compute completion_ratio and get completion_reason
    completion_ratio = len(main_turns) / max(interview.total_turns, 1)
    completion_reason = interview.completion_reason

    return InterviewReportResponse(
        overall_score=None if hosted_mode else round(overall_score, 2),
        content_score=None if hosted_mode else round(avg_content, 2),
        behavior_score=None if hosted_mode else round(avg_behavior, 2),
        final_score=None if hosted_mode else round(avg_final, 2),
        intent_score=round(avg_intent, 2) if avg_intent is not None else None,
        completion_ratio=None if hosted_mode else round(completion_ratio, 2),
        completion_reason=completion_reason,
        feedback_summary=feedback,
        turn_reviews=[] if hosted_mode else turn_reviews,
        total_turns=0 if hosted_mode else len(main_turns),
        followup_rate=0 if hosted_mode else round(followup_rate, 1),
        followup_interpretation=(
            "Retell-hosted interviews do not use EDI5 follow-up scoring."
            if hosted_mode
            else followup_interp
        ),
        is_edi5_scored=not hosted_mode,
        voice_mode=voice_mode,
        retell_transcript=metadata.get("retell_live_transcript"),
        retell_analysis=metadata.get("retell_analysis"),
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


# ── Include Retell Webhook Router ────────────────────────────────────────
from app.modules.interview.routers.retell_webhook import router as retell_webhook_router
router.include_router(retell_webhook_router)

# ── Include Interviewer Management Router ──────────────────────────────────
from app.modules.interview.routers.interviewer_management import router as interviewer_management_router
router.include_router(interviewer_management_router)
