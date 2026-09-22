"""
Assessment context and policy service layer for M2-E.

Provides context-aware session creation and policy resolution.
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.models.assessment_context import AssessmentContext, AssessmentPolicy
from app.models.assessment import AssessmentSession


# ── Policy Constants ──────────────────────────────────────────────────

MODE_PRACTICE = "practice"
MODE_PORTFOLIO = "portfolio_verification"
MODE_MOCK_DRIVE = "mock_drive"

PROGRESSION_INDEPENDENT = "independent"
PROGRESSION_SEQUENTIAL = "sequential"

DEFAULT_PRACTICE_POLICY_ID = 2  # Independent progression
LEGACY_PRACTICE_POLICY_ID = 1   # Sequential progression (for backfilled sessions)


# ── Policy Operations ─────────────────────────────────────────────────

def get_policy(db: Session, policy_id: int) -> Optional[AssessmentPolicy]:
    """Fetch a policy by ID."""
    return db.query(AssessmentPolicy).filter(AssessmentPolicy.id == policy_id).first()


def get_default_practice_policy(db: Session) -> AssessmentPolicy:
    """Get the default practice policy (independent progression, unlimited attempts)."""
    policy = get_policy(db, DEFAULT_PRACTICE_POLICY_ID)
    if policy is None:
        raise ValueError(f"Default practice policy (id={DEFAULT_PRACTICE_POLICY_ID}) not found")
    return policy


def create_policy(
    db: Session,
    name: str,
    session_duration_minutes: int = 180,
    round_duration_minutes: int = 30,
    max_attempts: Optional[int] = None,
    resume_allowed: bool = True,
    exit_allowed: bool = True,
    progression_mode: str = PROGRESSION_SEQUENTIAL,
    progression_config: Optional[dict] = None,
) -> AssessmentPolicy:
    """Create a new assessment policy."""
    policy = AssessmentPolicy(
        name=name,
        session_duration_minutes=session_duration_minutes,
        round_duration_minutes=round_duration_minutes,
        max_attempts=max_attempts,
        resume_allowed=resume_allowed,
        exit_allowed=exit_allowed,
        progression_mode=progression_mode,
        progression_config=progression_config or {},
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


# ── Context Operations ────────────────────────────────────────────────

def get_context(db: Session, context_id: int) -> Optional[AssessmentContext]:
    """Fetch a context by ID."""
    return db.query(AssessmentContext).filter(AssessmentContext.id == context_id).first()


def get_or_create_practice_context(
    db: Session,
    user_id: int,
    policy_id: Optional[int] = None,
) -> AssessmentContext:
    """Get or create a practice context for the user.
    
    Practice uses independent round semantics:
    - Unlimited attempts
    - Independent rounds (no forced progression)
    - Student can choose any round to practice
    """
    if policy_id is None:
        policy_id = DEFAULT_PRACTICE_POLICY_ID
    
    # For practice, we create a new context per attempt
    # This allows independent tracking of practice sessions
    context = AssessmentContext(
        mode=MODE_PRACTICE,
        purpose="practice",
        student_id=user_id,
        policy_id=policy_id,
        status="active",
    )
    db.add(context)
    db.commit()
    db.refresh(context)
    return context


def create_context(
    db: Session,
    mode: str,
    policy_id: int,
    student_id: Optional[int] = None,
    created_by_id: Optional[int] = None,
    purpose: Optional[str] = None,
    company_name: Optional[str] = None,
    target_role: Optional[str] = None,
    jd_text: Optional[str] = None,
    availability_start: Optional[datetime] = None,
    availability_end: Optional[datetime] = None,
) -> AssessmentContext:
    """Create a new assessment context.
    
    Generic context creation for portfolio/mock_drive/structured assessments.
    """
    context = AssessmentContext(
        mode=mode,
        purpose=purpose,
        student_id=student_id,
        created_by_id=created_by_id,
        company_name=company_name,
        target_role=target_role,
        jd_text=jd_text,
        availability_start=availability_start,
        availability_end=availability_end,
        policy_id=policy_id,
        status="active",
    )
    db.add(context)
    db.commit()
    db.refresh(context)
    return context


def complete_context(db: Session, context_id: int) -> Optional[AssessmentContext]:
    """Mark a context as completed."""
    context = get_context(db, context_id)
    if context is None:
        return None
    
    if context.status != "completed":
        context.status = "completed"
        context.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(context)
    
    return context


# ── Policy Resolution ─────────────────────────────────────────────────

def get_session_duration_minutes(context: AssessmentContext) -> int:
    """Get session duration from context policy."""
    return context.policy.session_duration_minutes


def get_round_duration_minutes(context: AssessmentContext) -> int:
    """Get round duration from context policy."""
    return context.policy.round_duration_minutes


def get_max_attempts(context: AssessmentContext) -> Optional[int]:
    """Get attempt limit from context policy. None = unlimited."""
    return context.policy.max_attempts


def is_resume_allowed(context: AssessmentContext) -> bool:
    """Check if resume is allowed by policy."""
    return context.policy.resume_allowed


def is_exit_allowed(context: AssessmentContext) -> bool:
    """Check if exit is allowed by policy."""
    return context.policy.exit_allowed


def get_progression_mode(context: AssessmentContext) -> str:
    """Get progression mode: 'independent' or 'sequential'."""
    return context.policy.progression_mode


def get_progression_config(context: AssessmentContext) -> dict:
    """Get progression configuration (e.g., round order for sequential)."""
    return context.policy.progression_config


# ── Availability Enforcement ──────────────────────────────────────────

def is_context_available(context: AssessmentContext, check_time: Optional[datetime] = None) -> bool:
    """Check if context is available at the given time.
    
    Returns True if:
    - No availability window is set, OR
    - Current time is within [availability_start, availability_end]
    """
    if check_time is None:
        check_time = datetime.utcnow()
    
    if context.availability_start and check_time < context.availability_start:
        return False
    
    if context.availability_end and check_time > context.availability_end:
        return False
    
    return True


def get_effective_expiry(
    context: AssessmentContext,
    session_start: datetime,
) -> datetime:
    """Calculate effective session expiry respecting both duration and availability window."""
    duration_minutes = get_session_duration_minutes(context)
    duration_expiry = session_start + timedelta(minutes=duration_minutes)
    
    if context.availability_end:
        return min(duration_expiry, context.availability_end)
    
    return duration_expiry


# ── Attempt Counting ──────────────────────────────────────────────────

def get_attempt_count(db: Session, context_id: int) -> int:
    """Count completed sessions for a context."""
    return (
        db.query(AssessmentSession)
        .filter(
            AssessmentSession.context_id == context_id,
            AssessmentSession.status == "completed",
        )
        .count()
    )


def can_create_attempt(db: Session, context: AssessmentContext) -> bool:
    """Check if another attempt is allowed by policy."""
    max_attempts = get_max_attempts(context)
    
    if max_attempts is None:
        return True  # Unlimited attempts
    
    current_attempts = get_attempt_count(db, context.id)
    return current_attempts < max_attempts
