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
from app.models.interview import (
    InterviewSession,
    ApprovedQuestionPool,
    InterviewTurn,
)
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
)
from app.modules.interview.services.interview_rl_engine import InterviewRLEngine

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/interview",
    tags=["Interview Round"],
)

# Global instances (will be set by app lifespan)
ml_models = {}  # To be populated by app/main.py
groq_service = GroqService(settings.GROQ_API_KEY)

# Redis client for caching questions and TTS
try:
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=False)
except Exception as e:
    logger.warning(f"Redis connection failed: {str(e)} - caching disabled")
    redis_client = None


# ── ENDPOINT 1: POST /interview/resume/upload ──────────────────────────
@router.post("/resume/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    session_id: Optional[int] = Query(None, description="Assessment session ID (optional)"),
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
            approved_at=datetime.utcnow(),
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
        pool.approved_at = datetime.utcnow()

    db.commit()

    return ApprovePoolResponse(
        status="approved" if req.approved else "rejected"
    )


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

    rl_engine = InterviewRLEngine()
    interview = InterviewSession(
        session_id=session_id,
        phase="HR",
        current_turn=0,
        total_turns=10,
        rl_state=rl_engine.to_dict(),
    )
    db.add(interview)
    db.commit()
    db.refresh(interview)

    return StartInterviewResponse(
        interview_id=interview.id,
        phase="HR",
        total_turns=10,
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
    cache_key = f"question:{hashlib.md5(question_text.encode()).hexdigest()}:{difficulty}"
    rephrased = None

    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                rephrased = cached.decode()
        except Exception as e:
            logger.warning(f"Redis get failed: {str(e)}")

    if not rephrased:
        rephrased = groq_service.rephrase_question(question_text, difficulty)
        if redis_client:
            try:
                redis_client.setex(cache_key, 86400, rephrased)
            except Exception as e:
                logger.warning(f"Redis set failed: {str(e)}")

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
    interview = db.query(InterviewSession).filter(
        InterviewSession.id == interview_id
    ).first()

    if not interview:
        raise HTTPException(status_code=404, detail="Interview not found")

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
        classifier_result = groq_service.classify_answer(question, transcript)
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
        approved_pool = db.query(ApprovedQuestionPool).filter(
            ApprovedQuestionPool.session_id == interview.session_id,
            ApprovedQuestionPool.admin_approved == True,
        ).first()

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

    return InterviewReportResponse(
        overall_score=round(overall_score, 2),
        content_score=round(avg_content, 2),
        behavior_score=round(avg_behavior, 2),
        final_score=round(avg_final, 2),
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
