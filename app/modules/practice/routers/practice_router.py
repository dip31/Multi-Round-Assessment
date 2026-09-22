"""
Practice Assessment Router — EDI5 M2-B + M2-E

Orchestrates a complete Practice assessment end-to-end with context awareness.

M2-E Changes:
- Practice now creates/uses AssessmentContext
- Mode identified by context, not route
- Independent round progression (no forced aptitude → coding → interview)
- Policy-driven timing and rules

Design rules:
- Reuses AssessmentSession / AssessmentRound from M2-A.
- Reuses existing Aptitude, Coding, and Interview module logic.
- Backend controls round ordering and session completion.
- Idempotent: repeated calls return existing active state.
- Ownership enforced on every mutation.
- Backend-authoritative expiration via persisted expires_at.
- Practice supports multiple completed attempts (no overwrite).
- Practice supports independent round selection.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.database.db import get_db
from app.models.assessment import AssessmentRound, AssessmentSession
from app.models.user import User
from app.schemas.assessment import RoundResponse, SessionResponse
from app.services.session_service import (
    advance_to_next_round,
    complete_round,
    complete_session,
    create_round,
    create_session,
    get_active_round,
    get_active_session,
    get_owned_round,
    get_owned_session,
    get_user_active_round,
    start_round,
)
from app.services.assessment_context_service import (
    get_or_create_practice_context,
    get_default_practice_policy,
    is_context_available,
    can_create_attempt,
)
from app.modules.practice.services.practice_result_service import (
    get_round_result_summary,
    get_round_detailed_review,
)

router = APIRouter(prefix="/practice", tags=["Practice Assessment"])

# Legacy round ordering for backward compatibility with existing tests.
# M2-E: Practice no longer requires this sequence; rounds are independent.
ROUND_ORDER: List[str] = ["aptitude", "coding", "interview"]


def _next_round_type(current_type: str) -> Optional[str]:
    """Return the round type that follows current_type, or None if last."""
    try:
        idx = ROUND_ORDER.index(current_type)
    except ValueError:
        return None
    next_idx = idx + 1
    return ROUND_ORDER[next_idx] if next_idx < len(ROUND_ORDER) else None


# ── Response schemas ──────────────────────────────────────────────────

class PracticeStatusResponse(BaseModel):
    session_id: int
    session_status: str
    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_score: float
    active_round: Optional[RoundResponse] = None
    rounds: List[RoundResponse] = []
    is_reconnect: bool = False

    model_config = {"from_attributes": True}


class PracticeStartRequest(BaseModel):
    round_type: str


class PracticeStartResponse(BaseModel):
    session_id: int
    session_status: str
    active_round: RoundResponse
    is_new: bool
    message: str

    model_config = {"from_attributes": True}


class AdvanceRoundRequest(BaseModel):
    """Client signals current round is done; backend decides what comes next."""
    current_round_id: int


class AdvanceRoundResponse(BaseModel):
    previous_round_id: int
    previous_round_status: str
    next_round: Optional[RoundResponse] = None
    session_status: str
    session_completed: bool
    message: str

    model_config = {"from_attributes": True}


class CompleteRoundRequest(BaseModel):
    round_id: int
    round_type: str  # aptitude | coding | interview


class CompleteRoundResponse(BaseModel):
    round_id: int
    round_status: str
    session_status: str
    session_completed: bool
    next_round: Optional[RoundResponse] = None
    message: str

    model_config = {"from_attributes": True}


# ── Helpers ───────────────────────────────────────────────────────────

def _require_session_not_expired(session: AssessmentSession) -> None:
    """Raise 410 if session is expired or terminated."""
    if session.status in {"expired", "terminated"}:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=f"Assessment session has {session.status}. Start a new practice attempt.",
        )


def _require_round_active(assessment_round: AssessmentRound) -> None:
    """Raise 410 if a round is no longer active."""
    if assessment_round.status == "expired":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="This assessment round has expired. Contact support or start a new attempt.",
        )
    if assessment_round.status in {"terminated", "completed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Round is already {assessment_round.status}.",
        )


def _get_active_round_response(
    db: Session, session: AssessmentSession
) -> Optional[RoundResponse]:
    active = get_active_round(db, session.id)
    if active is None:
        return None
    return RoundResponse.model_validate(active)


# ── Endpoints ─────────────────────────────────────────────────────────

@router.post(
    "/start",
    response_model=PracticeStartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start or resume a Practice assessment",
)
def start_practice(
    payload: PracticeStartRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PracticeStartResponse:
    """Idempotent practice start with context awareness.

    M2-E: Creates an AssessmentContext for practice mode.
    
    - If the user has no active session: creates context + session, activates selected round.
    - If the user already has an active session: returns existing state (resume) if matching round type.
    - Returns HTTP 409 if a different round type is already active.
    - Returns HTTP 200 on resume, HTTP 201 on new session.
    """
    if payload.round_type not in {"aptitude", "coding", "interview"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid round type. Must be aptitude, coding, or interview.",
        )

    existing_session = get_active_session(db, current_user.id)

    if existing_session is not None:
        # Resume: return existing active session and round.
        _require_session_not_expired(existing_session)
        active_round = get_active_round(db, existing_session.id)
        if active_round is None:
            # Session is active but no active round — shouldn't normally happen,
            # but handle gracefully by re-activating the first incomplete round.
            # Check if all rounds are completed → session should have been completed.
            completed_rounds = [
                r for r in existing_session.rounds if r.status == "completed"
            ]
            completed_types = {r.round_type for r in completed_rounds}
            # Find the next round in order that hasn't been completed yet.
            next_type = None
            for rt in ROUND_ORDER:
                if rt not in completed_types:
                    next_type = rt
                    break
            if next_type is not None:
                active_round = start_round(db, existing_session.id, next_type)
            else:
                # All rounds completed but session not marked complete — fix it.
                complete_session(db, existing_session.id, current_user.id)
                db.refresh(existing_session)
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="All rounds are complete. Session has been completed. Start a new practice attempt.",
                )
        else:
            if active_round.round_type != payload.round_type:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"An active {active_round.round_type} round is already in progress. Please complete or finish it before starting a {payload.round_type} round.",
                )

        from fastapi import Response as FastAPIResponse
        # FastAPI doesn't support changing status_code mid-function easily,
        # so we use a workaround: the client receives 200 on resume.
        # We signal resume via is_new=False.
        return PracticeStartResponse(
            session_id=existing_session.id,
            session_status=existing_session.status,
            active_round=RoundResponse.model_validate(active_round),
            is_new=False,
            message=f"Resuming active {active_round.round_type} round.",
        )

    # New session: create context + session + activate first round.
    # M2-E: Create practice context
    context = get_or_create_practice_context(db, current_user.id)
    
    # Check availability (practice has no restrictions, but enforce for future modes)
    if not is_context_available(context):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Practice assessment is not currently available.",
        )
    
    # Check attempt limits (practice is unlimited, but enforce for future modes)
    if not can_create_attempt(db, context):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Maximum attempts reached for this assessment.",
        )
    
    # Create session with context
    new_session = create_session(db, user_id=current_user.id, context_id=context.id)
    
    progression_mode = context.policy.progression_mode if context.policy else "sequential"
    if progression_mode == "independent":
        round_type_to_start = payload.round_type
    else:
        round_type_to_start = ROUND_ORDER[0]
        
    first_round = start_round(db, new_session.id, round_type_to_start)

    return PracticeStartResponse(
        session_id=new_session.id,
        session_status=new_session.status,
        active_round=RoundResponse.model_validate(first_round),
        is_new=True,
        message=f"Practice assessment started. {first_round.round_type.capitalize()} round is active.",
    )


@router.get(
    "/status",
    response_model=PracticeStatusResponse,
    summary="Get current practice session status",
)
def get_practice_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PracticeStatusResponse:
    """Return current session state, all rounds, and active round.

    Works for both in-progress and just-completed sessions.
    If no active session exists, returns latest session (for dashboards).
    """
    session = get_active_session(db, current_user.id)
    is_reconnect = False

    if session is None:
        # Return latest session for dashboard continuity.
        session = (
            db.query(AssessmentSession)
            .filter(AssessmentSession.user_id == current_user.id)
            .order_by(AssessmentSession.id.desc())
            .first()
        )
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No practice assessment session found. Start one via POST /practice/start",
            )
        is_reconnect = True

    active_round = get_active_round(db, session.id) if session.status == "in_progress" else None

    return PracticeStatusResponse(
        session_id=session.id,
        session_status=session.status,
        started_at=session.started_at,
        expires_at=session.expires_at,
        completed_at=session.completed_at,
        total_score=session.total_score,
        active_round=RoundResponse.model_validate(active_round) if active_round else None,
        rounds=[RoundResponse.model_validate(r) for r in session.rounds],
        is_reconnect=is_reconnect,
    )


@router.post(
    "/complete-round",
    response_model=CompleteRoundResponse,
    summary="Complete the current round and advance to next",
)
def complete_practice_round(
    payload: CompleteRoundRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CompleteRoundResponse:
    """Complete the specified round and activate the next one.

    Backend controls progression:
    - aptitude → coding
    - coding → interview
    - interview → session completed

    Idempotent: completing an already-completed round returns the current state.
    Authorization: verifies the round belongs to the authenticated user.
    Expiration: expired rounds cannot be completed.
    """
    # Ownership check.
    assessment_round = get_owned_round(db, payload.round_id, current_user.id)
    if assessment_round is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Round not found or does not belong to you.",
        )

    # Expiration guard.
    if assessment_round.status == "expired":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Cannot complete an expired round.",
        )

    # Idempotent: already completed.
    if assessment_round.status == "completed":
        session = get_owned_session(db, assessment_round.session_id, current_user.id)
        next_type = _next_round_type(assessment_round.round_type)
        next_round = None
        if next_type and session and session.status == "in_progress":
            active = get_active_round(db, session.id)
            if active and active.round_type == next_type:
                next_round = RoundResponse.model_validate(active)
        return CompleteRoundResponse(
            round_id=assessment_round.id,
            round_status="completed",
            session_status=session.status if session else "unknown",
            session_completed=(session.status == "completed") if session else False,
            next_round=next_round,
            message="Round was already completed.",
        )

    # Validate round_type matches.
    if assessment_round.round_type != payload.round_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"round_type mismatch: expected {assessment_round.round_type}, got {payload.round_type}",
        )

    # Session must be in_progress.
    session = get_owned_session(db, assessment_round.session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    _require_session_not_expired(session)

    # Complete the round.
    completed = complete_round(db, assessment_round.id, current_user.id)
    if completed is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to complete round.")

    context_obj = None
    if session.context_id:
        from app.services.assessment_context_service import get_context
        context_obj = get_context(db, session.context_id)
        
    progression_mode = context_obj.policy.progression_mode if context_obj and context_obj.policy else "sequential"

    if progression_mode == "independent":
        # Independent practice: complete session immediately, no next round.
        _finalize_session_score(db, session.id)
        completed_sess = complete_session(db, session.id, current_user.id)
        session_completed = True
        next_round_obj = None
        message = f"{payload.round_type.capitalize()} round completed. Independent practice session finished."
        if completed_sess:
            db.refresh(completed_sess)
            session = completed_sess
    else:
        next_type = _next_round_type(payload.round_type)
        next_round_obj = None
        session_completed = False

        if next_type is not None:
            # Activate the next round.
            next_round_obj = start_round(db, session.id, next_type)
            message = f"{payload.round_type.capitalize()} round completed. {next_type.capitalize()} round activated."
        else:
            # Interview was the last round — complete the session.
            _finalize_session_score(db, session.id)
            completed_sess = complete_session(db, session.id, current_user.id)
            session_completed = True
            message = "Interview round completed. Practice assessment complete. Well done!"
            if completed_sess:
                db.refresh(completed_sess)
                session = completed_sess

    db.refresh(session)

    return CompleteRoundResponse(
        round_id=completed.id,
        round_status=completed.status,
        session_status=session.status,
        session_completed=session_completed,
        next_round=RoundResponse.model_validate(next_round_obj) if next_round_obj else None,
        message=message,
    )


@router.post(
    "/advance",
    response_model=AdvanceRoundResponse,
    summary="Advance from current round to next (alternative to complete-round)",
)
def advance_practice_round(
    payload: AdvanceRoundRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AdvanceRoundResponse:
    """Complete current round and activate next using advance_to_next_round.

    Thin wrapper over the M2-A advance_to_next_round service.
    Authorization: verifies round ownership.
    """
    assessment_round = get_owned_round(db, payload.current_round_id, current_user.id)
    if assessment_round is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Round not found or does not belong to you.",
        )

    if assessment_round.status == "expired":
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Cannot advance from an expired round.",
        )

    session = get_owned_session(db, assessment_round.session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
    _require_session_not_expired(session)

    next_type = _next_round_type(assessment_round.round_type)

    context_obj = None
    if session.context_id:
        from app.services.assessment_context_service import get_context
        context_obj = get_context(db, session.context_id)
        
    progression_mode = context_obj.policy.progression_mode if context_obj and context_obj.policy else "sequential"

    if progression_mode == "independent":
        if assessment_round.status != "completed":
            complete_round(db, assessment_round.id, current_user.id)
        _finalize_session_score(db, session.id)
        complete_session(db, session.id, current_user.id)
        db.refresh(session)
        return AdvanceRoundResponse(
            previous_round_id=assessment_round.id,
            previous_round_status="completed",
            next_round=None,
            session_status=session.status,
            session_completed=True,
            message="Independent practice: no automatic next round.",
        )

    if next_type is None:
        # No next round: complete session.
        if assessment_round.status != "completed":
            complete_round(db, assessment_round.id, current_user.id)
        _finalize_session_score(db, session.id)
        complete_session(db, session.id, current_user.id)
        db.refresh(session)
        return AdvanceRoundResponse(
            previous_round_id=assessment_round.id,
            previous_round_status="completed",
            next_round=None,
            session_status=session.status,
            session_completed=True,
            message="Final round completed. Practice assessment complete.",
        )

    next_round = advance_to_next_round(db, session.id, next_type)
    db.refresh(assessment_round)
    db.refresh(session)

    return AdvanceRoundResponse(
        previous_round_id=assessment_round.id,
        previous_round_status=assessment_round.status,
        next_round=RoundResponse.model_validate(next_round),
        session_status=session.status,
        session_completed=False,
        message=f"Advanced to {next_type} round.",
    )


@router.get(
    "/history",
    summary="List all practice attempts for the authenticated user",
)
def get_practice_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list:
    """Return all practice attempts (sessions) for this user, ordered newest first.

    Multiple completed attempts are preserved separately.
    """
    sessions = (
        db.query(AssessmentSession)
        .filter(AssessmentSession.user_id == current_user.id)
        .order_by(AssessmentSession.id.desc())
        .all()
    )
    result = []
    for sess in sessions:
        rounds_summary = [
            {
                "id": r.id,
                "round_type": r.round_type,
                "status": r.status,
                "score": r.score,
                "started_at": r.started_at,
                "completed_at": r.completed_at,
            }
            for r in sess.rounds
        ]
        result.append({
            "session_id": sess.id,
            "status": sess.status,
            "total_score": sess.total_score,
            "started_at": sess.started_at,
            "completed_at": sess.completed_at,
            "rounds": rounds_summary,
        })
    return result


@router.get(
    "/session/{session_id}/round/{round_id}/result",
    summary="Get result summary for a completed practice round",
)
def get_practice_round_result(
    session_id: int,
    round_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return historical result summary for a completed round."""
    # Enforce ownership
    session = get_owned_session(db, session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or not owned by user.")
    
    result = get_round_result_summary(db, session_id, round_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Round result not found or round not yet completed.",
        )
    return result


@router.get(
    "/session/{session_id}/round/{round_id}/review",
    summary="Get detailed question-by-question review for a completed practice round",
)
def get_practice_round_review(
    session_id: int,
    round_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return detailed review for a completed round."""
    # Enforce ownership
    session = get_owned_session(db, session_id, current_user.id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or not owned by user.")

    review = get_round_detailed_review(db, session_id, round_id)
    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Round review not found or round not yet completed.",
        )
    return review


# ── Internal helpers ──────────────────────────────────────────────────

def _finalize_session_score(db: Session, session_id: int) -> None:
    """Compute session total_score as mean of completed round scores."""
    from sqlalchemy import func
    avg = (
        db.query(func.avg(AssessmentRound.score))
        .filter(
            AssessmentRound.session_id == session_id,
            AssessmentRound.status == "completed",
        )
        .scalar()
    )
    sess = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if sess is not None:
        sess.total_score = float(avg or 0.0)
        db.commit()
