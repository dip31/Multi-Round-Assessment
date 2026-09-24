"""Authoritative assessment session and round lifecycle operations.

M2-E: Context-aware session creation with policy-driven timing.
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.models.assessment import AssessmentRound, AssessmentSession
from app.models.assessment_context import AssessmentContext


SESSION_TIMEOUT_MINUTES: int = getattr(settings, "SESSION_TIMEOUT_MINUTES", 180)
ROUND_TIMEOUT_MINUTES: int = getattr(
    settings, "ASSESSMENT_ROUND_TIMEOUT_MINUTES", 30
)

SESSION_STATES = {"not_started", "in_progress", "completed", "terminated", "expired"}
ROUND_STATES = {"pending", "active", "completed", "terminated", "expired"}


def _now() -> datetime:
    """Return a naive UTC timestamp matching the existing DateTime columns."""
    return datetime.utcnow()


def _session_expiry(started_at: datetime, context: Optional[AssessmentContext] = None) -> datetime:
    """Calculate session expiry from policy or fallback to global config."""
    if context and context.policy:
        duration_minutes = context.policy.session_duration_minutes
    else:
        duration_minutes = SESSION_TIMEOUT_MINUTES
    
    expiry = started_at + timedelta(minutes=duration_minutes)
    
    # Respect availability window if set
    if context and context.availability_end:
        expiry = min(expiry, context.availability_end)
    
    return expiry


def _round_expiry(started_at: datetime, context: Optional[AssessmentContext] = None) -> datetime:
    """Calculate round expiry from policy or fallback to global config."""
    if context and context.policy:
        duration_minutes = context.policy.round_duration_minutes
    else:
        duration_minutes = ROUND_TIMEOUT_MINUTES
    
    return started_at + timedelta(minutes=duration_minutes)


def _expire_stale_session(db: Session, user_id: int) -> None:
    """Expire stale sessions and their active rounds using backend time."""
    now = _now()
    stale = (
        db.query(AssessmentSession)
        .filter(
            AssessmentSession.user_id == user_id,
            AssessmentSession.status == "in_progress",
            (
                (AssessmentSession.expires_at.isnot(None))
                & (AssessmentSession.expires_at <= now)
            )
            | (
                AssessmentSession.expires_at.is_(None)
                & (AssessmentSession.started_at <= now - timedelta(minutes=SESSION_TIMEOUT_MINUTES))
            ),
        )
        .all()
    )
    for session in stale:
        session.status = "expired"
        session.completed_at = now
        db.query(AssessmentRound).filter(
            AssessmentRound.session_id == session.id,
            AssessmentRound.status == "active",
        ).update(
            {"status": "expired", "completed_at": now},
            synchronize_session="fetch",
        )
    if stale:
        db.commit()


def _expire_stale_rounds(db: Session, session_id: int) -> None:
    """Expire overdue active rounds before returning them to callers."""
    now = _now()
    db.query(AssessmentRound).filter(
        AssessmentRound.session_id == session_id,
        AssessmentRound.status == "active",
        AssessmentRound.expires_at.isnot(None),
        AssessmentRound.expires_at <= now,
    ).update(
        {"status": "expired", "completed_at": now},
        synchronize_session="fetch",
    )
    db.commit()


def get_owned_session(
    db: Session,
    session_id: int,
    user_id: int,
    *,
    for_update: bool = False,
) -> Optional[AssessmentSession]:
    """Load a session only when it belongs to the authenticated user."""
    query = db.query(AssessmentSession).filter(
        AssessmentSession.id == session_id,
        AssessmentSession.user_id == user_id,
    )
    if for_update:
        query = query.with_for_update()
    return query.first()


def get_owned_round(
    db: Session,
    round_id: int,
    user_id: int,
    *,
    for_update: bool = False,
) -> Optional[AssessmentRound]:
    """Load a round only through its owning session and authenticated user."""
    query = (
        db.query(AssessmentRound)
        .join(AssessmentSession, AssessmentSession.id == AssessmentRound.session_id)
        .filter(
            AssessmentRound.id == round_id,
            AssessmentSession.user_id == user_id,
        )
    )
    if for_update:
        query = query.with_for_update()
    return query.first()


def get_active_session(
    db: Session, user_id: int, *, for_update: bool = False
) -> Optional[AssessmentSession]:
    """Return the user's active session, expiring it first when necessary."""
    _expire_stale_session(db, user_id)
    query = db.query(AssessmentSession).filter(
        AssessmentSession.user_id == user_id,
        AssessmentSession.status == "in_progress",
    )
    if for_update:
        query = query.with_for_update()
    return query.order_by(AssessmentSession.id.desc()).first()


def create_session(db: Session, user_id: int, context_id: Optional[int] = None) -> AssessmentSession:
    """Start or return the user's existing active session idempotently.
    
    M2-E: Context-aware session creation.
    - If context_id provided, uses policy from context
    - Otherwise falls back to legacy behavior
    """
    existing = get_active_session(db, user_id, for_update=True)
    if existing is not None:
        return existing

    started_at = _now()
    
    # Fetch context for policy-driven timing
    context = None
    if context_id:
        context = db.query(AssessmentContext).filter(AssessmentContext.id == context_id).first()
    
    session = AssessmentSession(
        user_id=user_id,
        context_id=context_id,
        status="in_progress",
        started_at=started_at,
        expires_at=_session_expiry(started_at, context),
    )
    db.add(session)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = get_active_session(db, user_id)
        if existing is None:
            raise
        return existing
    db.refresh(session)
    return session


def complete_session(
    db: Session,
    session_id: int,
    user_id: int | None = None,
) -> Optional[AssessmentSession]:
    """Complete a session; repeated completion is safe and has no side effects."""
    query = db.query(AssessmentSession).filter(AssessmentSession.id == session_id)
    if user_id is not None:
        query = query.filter(AssessmentSession.user_id == user_id)
    session = query.with_for_update().first()
    if session is None:
        return None
    if session.status == "completed":
        return session
    if session.status in {"expired", "terminated"}:
        raise ValueError(f"Cannot complete a {session.status} session")
    if session.status != "in_progress":
        raise ValueError(f"Invalid session transition from {session.status}")

    now = _now()
    session.status = "completed"
    session.completed_at = now
    db.query(AssessmentRound).filter(
        AssessmentRound.session_id == session.id,
        AssessmentRound.status == "active",
    ).update({"status": "completed", "completed_at": now}, synchronize_session="fetch")
    db.commit()
    db.refresh(session)
    return session


def expire_session(
    db: Session,
    session_id: int,
    user_id: int | None = None,
) -> Optional[AssessmentSession]:
    """Expire an active session and its active round exactly once."""
    query = db.query(AssessmentSession).filter(AssessmentSession.id == session_id)
    if user_id is not None:
        query = query.filter(AssessmentSession.user_id == user_id)
    session = query.with_for_update().first()
    if session is None:
        return None
    if session.status == "expired":
        return session
    if session.status != "in_progress":
        raise ValueError(f"Invalid session expiration from {session.status}")
    now = _now()
    session.status = "expired"
    session.completed_at = now
    db.query(AssessmentRound).filter(
        AssessmentRound.session_id == session.id,
        AssessmentRound.status == "active",
    ).update({"status": "expired", "completed_at": now}, synchronize_session="fetch")
    db.commit()
    db.refresh(session)
    return session


def get_round(
    db: Session,
    round_id: int,
    user_id: int | None = None,
) -> Optional[AssessmentRound]:
    if user_id is None:
        return db.query(AssessmentRound).filter(AssessmentRound.id == round_id).first()
    return get_owned_round(db, round_id, user_id)


def get_active_round(
    db: Session,
    session_id: int,
    *,
    for_update: bool = False,
) -> Optional[AssessmentRound]:
    _expire_stale_rounds(db, session_id)
    query = db.query(AssessmentRound).filter(
        AssessmentRound.session_id == session_id,
        AssessmentRound.status == "active",
    )
    if for_update:
        query = query.with_for_update()
    return query.order_by(AssessmentRound.id.desc()).first()


def start_round(
    db: Session,
    session_id: int,
    round_type: str,
    practice_type: Optional[str] = None,
) -> AssessmentRound:
    """Activate one round for an active session, idempotently.
    
    M2-E: Context-aware round expiry from policy.
    
    Args:
        practice_type: Optional practice variant (mcq/technical/combined/coding/interview)
                      Used for independent practice sessions to track the specific practice type
    """
    session = (
        db.query(AssessmentSession)
        .filter(AssessmentSession.id == session_id)
        .with_for_update()
        .first()
    )
    if session is None:
        raise ValueError("Assessment session not found")
    if session.status != "in_progress":
        raise ValueError(f"Cannot start a round for a {session.status} session")
    if session.expires_at and session.expires_at <= _now():
        session.status = "expired"
        session.completed_at = _now()
        db.commit()
        raise ValueError("Cannot start a round for an expired session")

    active = get_active_round(db, session_id, for_update=True)
    if active is not None:
        if active.round_type == round_type and active.practice_type == practice_type:
            return active
        raise ValueError("Another assessment round is already active")

    # For independent practice, always create a new round (don't reuse pending)
    # For sequential modes, check for pending round first
    pending = None
    if not practice_type:  # Only reuse pending for non-practice rounds
        pending = (
            db.query(AssessmentRound)
            .filter(
                AssessmentRound.session_id == session_id,
                AssessmentRound.round_type == round_type,
                AssessmentRound.status == "pending",
            )
            .with_for_update()
            .order_by(AssessmentRound.id.desc())
            .first()
        )
    
    started_at = _now()
    
    # Get context for policy-driven timing
    context = None
    if session.context_id:
        context = db.query(AssessmentContext).filter(AssessmentContext.id == session.context_id).first()
    
    assessment_round = pending or AssessmentRound(
        session_id=session_id,
        round_type=round_type,
        practice_type=practice_type,
        status="pending",
        started_at=started_at,
    )
    assessment_round.status = "active"
    assessment_round.started_at = started_at
    assessment_round.expires_at = _round_expiry(started_at, context)
    if practice_type and not pending:  # Set practice_type for new rounds
        assessment_round.practice_type = practice_type
    db.add(assessment_round)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = get_active_round(db, session_id)
        if existing is None:
            raise
        return existing
    db.refresh(assessment_round)
    return assessment_round


def create_round(db: Session, session_id: int, round_type: str) -> AssessmentRound:
    """Compatibility wrapper for existing module services."""
    return start_round(db, session_id, round_type)


def complete_round(
    db: Session,
    round_id: int,
    user_id: int | None = None,
) -> Optional[AssessmentRound]:
    """Complete an active round; repeated completion is idempotent."""
    query = db.query(AssessmentRound).filter(AssessmentRound.id == round_id)
    if user_id is not None:
        query = query.join(AssessmentSession).filter(
            AssessmentSession.user_id == user_id
        )
    assessment_round = query.with_for_update().first()
    if assessment_round is None:
        return None
    if assessment_round.status == "completed":
        return assessment_round
    if assessment_round.status in {"expired", "terminated"}:
        raise ValueError(f"Cannot complete a {assessment_round.status} round")
    if assessment_round.status != "active":
        raise ValueError(f"Invalid round transition from {assessment_round.status}")
    assessment_round.status = "completed"
    assessment_round.completed_at = _now()
    db.commit()
    db.refresh(assessment_round)
    return assessment_round


def end_round(
    db: Session,
    round_id: int,
    user_id: int | None = None,
) -> Optional[AssessmentRound]:
    """Compatibility wrapper for existing module services."""
    return complete_round(db, round_id, user_id)


def expire_round(
    db: Session,
    round_id: int,
    user_id: int | None = None,
) -> Optional[AssessmentRound]:
    """Expire an active round exactly once."""
    query = db.query(AssessmentRound).filter(AssessmentRound.id == round_id)
    if user_id is not None:
        query = query.join(AssessmentSession).filter(
            AssessmentSession.user_id == user_id
        )
    assessment_round = query.with_for_update().first()
    if assessment_round is None:
        return None
    if assessment_round.status == "expired":
        return assessment_round
    if assessment_round.status != "active":
        raise ValueError(f"Invalid round expiration from {assessment_round.status}")
    assessment_round.status = "expired"
    assessment_round.completed_at = _now()
    db.commit()
    db.refresh(assessment_round)
    return assessment_round


def advance_to_next_round(
    db: Session,
    session_id: int,
    next_round_type: str,
) -> AssessmentRound:
    """Complete the current round and activate exactly one next round."""
    session = (
        db.query(AssessmentSession)
        .filter(AssessmentSession.id == session_id)
        .with_for_update()
        .first()
    )
    if session is None:
        raise ValueError("Assessment session not found")
    if session.status != "in_progress":
        raise ValueError(f"Cannot advance a {session.status} session")
    active = get_active_round(db, session_id, for_update=True)
    if active is not None:
        if active.round_type == next_round_type:
            return active
        complete_round(db, active.id)
    return start_round(db, session_id, next_round_type)


def get_user_active_round(
    db: Session,
    user_id: int,
    round_type: str = "aptitude",
) -> Optional[AssessmentRound]:
    """Return an active round owned by the authenticated user."""
    active_session = get_active_session(db, user_id)
    if active_session is None:
        return None
    if round_type in ("aptitude", "mcq", "technical", "combined"):
        match_types = ["aptitude", "mcq", "technical", "combined"]
        query = AssessmentRound.round_type.in_(match_types)
    else:
        query = AssessmentRound.round_type == round_type
    _expire_stale_rounds(db, active_session.id)
    return (
        db.query(AssessmentRound)
        .filter(
            AssessmentRound.session_id == active_session.id,
            query,
            AssessmentRound.status == "active",
        )
        .first()
    )
