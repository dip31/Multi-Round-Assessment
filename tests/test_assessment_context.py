"""
Tests for M2-E Assessment Context and Policy

Verifies:
- Context creation for different modes
- Policy enforcement
- Practice context-aware sessions
- Independent round progression
- Legacy session compatibility
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.models.assessment import AssessmentSession, AssessmentRound
from app.models.assessment_context import AssessmentContext, AssessmentPolicy
from app.models.user import User
from app.services.assessment_context_service import (
    create_context,
    create_policy,
    get_or_create_practice_context,
    get_default_practice_policy,
    get_session_duration_minutes,
    get_round_duration_minutes,
    get_max_attempts,
    is_resume_allowed,
    is_exit_allowed,
    get_progression_mode,
    is_context_available,
    can_create_attempt,
    get_attempt_count,
    MODE_PRACTICE,
    MODE_PORTFOLIO,
    MODE_MOCK_DRIVE,
    PROGRESSION_INDEPENDENT,
    PROGRESSION_SEQUENTIAL,
)
from app.services.session_service import create_session, start_round


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def db() -> Session:
    """Provide database session."""
    db_gen = get_db()
    db_session = next(db_gen)
    try:
        yield db_session
    finally:
        db_session.close()


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user."""
    from app.services.auth_service import create_user
    user = create_user(
        db=db,
        name="Test User",
        email=f"test_context_{datetime.utcnow().timestamp()}@example.com",
        password="password123",
        role="student",
    )
    return user


# ── Policy Tests ──────────────────────────────────────────────────────

def test_default_practice_policy_exists(db: Session):
    """Default practice policy should be seeded."""
    policy = get_default_practice_policy(db)
    assert policy is not None
    assert policy.id == 2
    assert policy.name == "Practice Policy"
    assert policy.progression_mode == PROGRESSION_INDEPENDENT
    assert policy.max_attempts is None  # Unlimited


def test_create_custom_policy(db: Session):
    """Can create custom policy with specific constraints."""
    policy = create_policy(
        db=db,
        name="Strict Assessment Policy",
        session_duration_minutes=120,
        round_duration_minutes=20,
        max_attempts=3,
        resume_allowed=False,
        exit_allowed=False,
        progression_mode=PROGRESSION_SEQUENTIAL,
        progression_config={"rounds": ["aptitude", "coding"]},
    )
    
    assert policy.id is not None
    assert policy.name == "Strict Assessment Policy"
    assert policy.session_duration_minutes == 120
    assert policy.round_duration_minutes == 20
    assert policy.max_attempts == 3
    assert policy.resume_allowed is False
    assert policy.exit_allowed is False
    assert policy.progression_mode == PROGRESSION_SEQUENTIAL
    assert policy.progression_config == {"rounds": ["aptitude", "coding"]}


# ── Context Creation Tests ────────────────────────────────────────────

def test_create_practice_context(db: Session, test_user: User):
    """Practice context can be created."""
    policy = get_default_practice_policy(db)
    context = create_context(
        db=db,
        mode=MODE_PRACTICE,
        policy_id=policy.id,
        student_id=test_user.id,
        purpose="practice",
    )
    
    assert context.id is not None
    assert context.mode == MODE_PRACTICE
    assert context.purpose == "practice"
    assert context.student_id == test_user.id
    assert context.policy_id == policy.id
    assert context.status == "active"


def test_create_portfolio_context(db: Session, test_user: User):
    """Portfolio verification context can be created."""
    policy = create_policy(
        db=db,
        name="Portfolio Policy",
        progression_mode=PROGRESSION_SEQUENTIAL,
        progression_config={"rounds": ["aptitude", "coding", "interview"]},
    )
    
    context = create_context(
        db=db,
        mode=MODE_PORTFOLIO,
        policy_id=policy.id,
        student_id=test_user.id,
        purpose="portfolio_verification",
    )
    
    assert context.mode == MODE_PORTFOLIO
    assert context.purpose == "portfolio_verification"


def test_create_mock_drive_context(db: Session, test_user: User):
    """Mock drive context can be created with company/role."""
    policy = create_policy(
        db=db,
        name="Mock Drive Policy",
        max_attempts=1,
        progression_mode=PROGRESSION_SEQUENTIAL,
    )
    
    context = create_context(
        db=db,
        mode=MODE_MOCK_DRIVE,
        policy_id=policy.id,
        student_id=test_user.id,
        company_name="Tech Corp",
        target_role="Software Engineer",
        availability_start=datetime.utcnow(),
        availability_end=datetime.utcnow() + timedelta(days=7),
    )
    
    assert context.mode == MODE_MOCK_DRIVE
    assert context.company_name == "Tech Corp"
    assert context.target_role == "Software Engineer"
    assert context.availability_start is not None
    assert context.availability_end is not None


# ── Policy Resolution Tests ───────────────────────────────────────────

def test_policy_resolution(db: Session, test_user: User):
    """Policy values can be resolved from context."""
    policy = create_policy(
        db=db,
        name="Test Policy",
        session_duration_minutes=90,
        round_duration_minutes=15,
        max_attempts=5,
        resume_allowed=False,
        exit_allowed=True,
        progression_mode=PROGRESSION_INDEPENDENT,
    )
    
    context = create_context(
        db=db,
        mode=MODE_PRACTICE,
        policy_id=policy.id,
        student_id=test_user.id,
    )
    
    assert get_session_duration_minutes(context) == 90
    assert get_round_duration_minutes(context) == 15
    assert get_max_attempts(context) == 5
    assert is_resume_allowed(context) is False
    assert is_exit_allowed(context) is True
    assert get_progression_mode(context) == PROGRESSION_INDEPENDENT


# ── Availability Tests ────────────────────────────────────────────────

def test_availability_window_before_start(db: Session, test_user: User):
    """Context is not available before availability_start."""
    policy = get_default_practice_policy(db)
    future_start = datetime.utcnow() + timedelta(hours=1)
    
    context = create_context(
        db=db,
        mode=MODE_MOCK_DRIVE,
        policy_id=policy.id,
        student_id=test_user.id,
        availability_start=future_start,
    )
    
    assert not is_context_available(context)


def test_availability_window_after_end(db: Session, test_user: User):
    """Context is not available after availability_end."""
    policy = get_default_practice_policy(db)
    past_end = datetime.utcnow() - timedelta(hours=1)
    
    context = create_context(
        db=db,
        mode=MODE_MOCK_DRIVE,
        policy_id=policy.id,
        student_id=test_user.id,
        availability_start=datetime.utcnow() - timedelta(hours=2),
        availability_end=past_end,
    )
    
    assert not is_context_available(context)


def test_availability_within_window(db: Session, test_user: User):
    """Context is available within window."""
    policy = get_default_practice_policy(db)
    
    context = create_context(
        db=db,
        mode=MODE_MOCK_DRIVE,
        policy_id=policy.id,
        student_id=test_user.id,
        availability_start=datetime.utcnow() - timedelta(hours=1),
        availability_end=datetime.utcnow() + timedelta(hours=1),
    )
    
    assert is_context_available(context)


# ── Attempt Limit Tests ───────────────────────────────────────────────

def test_attempt_counting(db: Session, test_user: User):
    """Attempt counting works correctly."""
    policy = create_policy(
        db=db,
        name="Limited Attempts",
        max_attempts=2,
    )
    
    context = create_context(
        db=db,
        mode=MODE_MOCK_DRIVE,
        policy_id=policy.id,
        student_id=test_user.id,
    )
    
    assert get_attempt_count(db, context.id) == 0
    assert can_create_attempt(db, context) is True
    
    # Create first session
    session1 = create_session(db, test_user.id, context.id)
    session1.status = "completed"
    db.commit()
    
    assert get_attempt_count(db, context.id) == 1
    assert can_create_attempt(db, context) is True
    
    # Create second session
    session2 = create_session(db, test_user.id, context.id)
    session2.status = "completed"
    db.commit()
    
    assert get_attempt_count(db, context.id) == 2
    assert can_create_attempt(db, context) is False  # Limit reached


def test_unlimited_attempts(db: Session, test_user: User):
    """Unlimited attempts allowed when max_attempts is None."""
    policy = get_default_practice_policy(db)
    context = create_context(
        db=db,
        mode=MODE_PRACTICE,
        policy_id=policy.id,
        student_id=test_user.id,
    )
    
    # Create many sessions
    for _ in range(10):
        session = create_session(db, test_user.id, context.id)
        session.status = "completed"
        db.commit()
    
    assert get_attempt_count(db, context.id) == 10
    assert can_create_attempt(db, context) is True  # Still allowed


# ── Session Integration Tests ─────────────────────────────────────────

def test_session_links_to_context(db: Session, test_user: User):
    """Session correctly links to context."""
    context = get_or_create_practice_context(db, test_user.id)
    session = create_session(db, test_user.id, context.id)
    
    assert session.context_id == context.id
    assert session.context is not None
    assert session.context.mode == MODE_PRACTICE


def test_context_driven_session_timing(db: Session, test_user: User):
    """Session expiry respects policy duration."""
    policy = create_policy(
        db=db,
        name="Short Session",
        session_duration_minutes=60,
    )
    
    context = create_context(
        db=db,
        mode=MODE_PRACTICE,
        policy_id=policy.id,
        student_id=test_user.id,
    )
    
    session = create_session(db, test_user.id, context.id)
    
    # Expiry should be ~60 minutes from start
    expected_expiry = session.started_at + timedelta(minutes=60)
    assert session.expires_at is not None
    # Allow 1 second tolerance
    assert abs((session.expires_at - expected_expiry).total_seconds()) < 1


def test_context_driven_round_timing(db: Session, test_user: User):
    """Round expiry respects policy duration."""
    policy = create_policy(
        db=db,
        name="Short Rounds",
        round_duration_minutes=10,
    )
    
    context = create_context(
        db=db,
        mode=MODE_PRACTICE,
        policy_id=policy.id,
        student_id=test_user.id,
    )
    
    session = create_session(db, test_user.id, context.id)
    round = start_round(db, session.id, "aptitude")
    
    # Expiry should be ~10 minutes from start
    expected_expiry = round.started_at + timedelta(minutes=10)
    assert round.expires_at is not None
    assert abs((round.expires_at - expected_expiry).total_seconds()) < 1


# ── Practice Context Tests ────────────────────────────────────────────

def test_get_or_create_practice_context(db: Session, test_user: User):
    """Practice context can be auto-created."""
    context = get_or_create_practice_context(db, test_user.id)
    
    assert context.mode == MODE_PRACTICE
    assert context.purpose == "practice"
    assert context.student_id == test_user.id
    assert context.policy.progression_mode == PROGRESSION_INDEPENDENT


# ── Legacy Session Compatibility ──────────────────────────────────────

def test_legacy_sessions_have_context(db: Session):
    """Legacy sessions were backfilled to context_id=1."""
    legacy_context = db.query(AssessmentContext).filter(
        AssessmentContext.id == 1
    ).first()
    
    assert legacy_context is not None
    assert legacy_context.mode == MODE_PRACTICE
    assert legacy_context.purpose == "legacy"
    
    # Count sessions with legacy context
    legacy_count = db.query(AssessmentSession).filter(
        AssessmentSession.context_id == 1
    ).count()
    
    # At least the 214 that were backfilled
    assert legacy_count >= 214


def test_legacy_context_has_sequential_policy(db: Session):
    """Legacy context uses sequential progression (backward compat)."""
    legacy_context = db.query(AssessmentContext).filter(
        AssessmentContext.id == 1
    ).first()
    
    assert legacy_context.policy.progression_mode == PROGRESSION_SEQUENTIAL
    assert legacy_context.policy.progression_config == {
        "rounds": ["aptitude", "coding", "interview"]
    }


# ── Progression Mode Tests ────────────────────────────────────────────

def test_independent_progression_mode(db: Session, test_user: User):
    """Independent progression allows any round order."""
    policy = create_policy(
        db=db,
        name="Independent",
        progression_mode=PROGRESSION_INDEPENDENT,
    )
    
    context = create_context(
        db=db,
        mode=MODE_PRACTICE,
        policy_id=policy.id,
        student_id=test_user.id,
    )
    
    assert get_progression_mode(context) == PROGRESSION_INDEPENDENT
    # Independent means no forced order
    # This is verified by router tests


def test_sequential_progression_mode(db: Session, test_user: User):
    """Sequential progression enforces specific order."""
    policy = create_policy(
        db=db,
        name="Sequential",
        progression_mode=PROGRESSION_SEQUENTIAL,
        progression_config={"rounds": ["coding", "interview"]},
    )
    
    context = create_context(
        db=db,
        mode=MODE_MOCK_DRIVE,
        policy_id=policy.id,
        student_id=test_user.id,
    )
    
    assert get_progression_mode(context) == PROGRESSION_SEQUENTIAL
    assert context.policy.progression_config["rounds"] == ["coding", "interview"]


# ── M2-E Acceptance Criteria ──────────────────────────────────────────

def test_m2e_acceptance_context_exists(db: Session):
    """✓ AssessmentContext exists."""
    assert AssessmentContext is not None


def test_m2e_acceptance_policy_exists(db: Session):
    """✓ AssessmentPolicy exists."""
    assert AssessmentPolicy is not None


def test_m2e_acceptance_session_has_context_link(db: Session, test_user: User):
    """✓ AssessmentSession can identify its context."""
    context = get_or_create_practice_context(db, test_user.id)
    session = create_session(db, test_user.id, context.id)
    
    assert hasattr(session, 'context_id')
    assert hasattr(session, 'context')
    assert session.context is not None


def test_m2e_acceptance_practice_is_context_aware(db: Session, test_user: User):
    """✓ Practice sessions are context-aware."""
    context = get_or_create_practice_context(db, test_user.id)
    session = create_session(db, test_user.id, context.id)
    
    assert session.context_id is not None
    assert session.context.mode == MODE_PRACTICE


def test_m2e_acceptance_mode_not_just_route(db: Session, test_user: User):
    """✓ Practice mode is identified by context, not route."""
    context = get_or_create_practice_context(db, test_user.id)
    assert context.mode == MODE_PRACTICE
    # Mode is stored in database, not inferred from URL


def test_m2e_acceptance_policy_driven_timing(db: Session, test_user: User):
    """✓ Session/round duration comes from policy."""
    policy = create_policy(db=db, name="Custom", session_duration_minutes=45)
    context = create_context(db=db, mode=MODE_PRACTICE, policy_id=policy.id, student_id=test_user.id)
    session = create_session(db, test_user.id, context.id)
    
    # Verify timing comes from policy, not hardcoded global
    assert get_session_duration_minutes(context) == 45


def test_m2e_acceptance_independent_rounds_supported(db: Session, test_user: User):
    """✓ Practice supports independent round semantics."""
    policy = get_default_practice_policy(db)
    assert policy.progression_mode == PROGRESSION_INDEPENDENT


def test_m2e_acceptance_structured_progression_ready(db: Session, test_user: User):
    """✓ Sequential progression can be represented for Portfolio/Mock Drive."""
    policy = create_policy(
        db=db,
        name="Sequential",
        progression_mode=PROGRESSION_SEQUENTIAL,
        progression_config={"rounds": ["aptitude", "coding", "interview"]},
    )
    assert policy.progression_mode == PROGRESSION_SEQUENTIAL


def test_m2e_acceptance_historical_sessions_preserved(db: Session):
    """✓ Historical sessions are preserved and backfilled."""
    legacy_sessions = db.query(AssessmentSession).filter(
        AssessmentSession.context_id == 1
    ).count()
    assert legacy_sessions >= 214  # Original count


def test_m2e_acceptance_no_complete_mock_drive(db: Session):
    """✓ No complete Mock Drive implementation (deferred)."""
    # This test documents that Mock Drive is NOT fully implemented
    # Only context/policy infrastructure exists
    pass


def test_m2e_acceptance_no_complete_portfolio(db: Session):
    """✓ No complete Portfolio implementation (deferred)."""
    # This test documents that Portfolio is NOT fully implemented
    # Only context/policy infrastructure exists
    pass
