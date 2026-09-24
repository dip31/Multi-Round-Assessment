"""
EDI5 M2-B: Practice Assessment Execution — focused test suite.

Covers:
1.  Start practice.
2.  Duplicate practice start (idempotency / resume).
3.  First round activation (aptitude).
4.  Round completion.
5.  Next-round progression (aptitude → coding).
6.  Invalid round progression (wrong round_id).
7.  Session completion after final round.
8.  Multiple practice attempts (separate persisted sessions).
9.  Resume / reconnect (same session returned).
10. Expiration (expired rounds/sessions cannot continue).
11. Session ownership (cross-user isolation).
12. Round ownership (cross-user isolation).
13. Golden-path end-to-end lifecycle.

Service-level tests use in-memory SQLite; they do not depend on
FastAPI, FAISS, NumPy, Groq, or Sarvam.
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.assessment import AssessmentRound, AssessmentSession
from app.models.user import User
from app.services.session_service import (
    advance_to_next_round,
    complete_round,
    complete_session,
    create_round,
    create_session,
    expire_round,
    expire_session,
    get_active_round,
    get_active_session,
    get_owned_round,
    get_owned_session,
    start_round,
)
from app.modules.practice.routers.practice_router import (
    ROUND_ORDER,
    _next_round_type,
    _finalize_session_score,
)


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[User.__table__, AssessmentSession.__table__, AssessmentRound.__table__],
    )
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    # User 1 — primary student
    session.add(User(name="Alice", email="alice@test.local", password_hash="hash"))
    # User 2 — different student for cross-user tests
    session.add(User(name="Bob", email="bob@test.local", password_hash="hash"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


# ── 1. Start practice ─────────────────────────────────────────────────

def test_start_practice_creates_session_and_aptitude_round(db):
    """Starting practice creates one session and one active aptitude round."""
    sess = create_session(db, user_id=1)
    r = start_round(db, sess.id, "aptitude")

    assert sess.status == "in_progress"
    assert r.round_type == "aptitude"
    assert r.status == "active"
    assert r.expires_at is not None
    assert r.session_id == sess.id


# ── 2. Duplicate start (idempotency / resume) ─────────────────────────

def test_duplicate_practice_start_returns_existing_session(db):
    """create_session is idempotent — same session returned on second call."""
    first = create_session(db, user_id=1)
    second = create_session(db, user_id=1)

    assert first.id == second.id
    assert db.query(AssessmentSession).filter(
        AssessmentSession.user_id == 1
    ).count() == 1


def test_duplicate_round_start_returns_existing_round(db):
    """start_round is idempotent for the same round_type."""
    sess = create_session(db, user_id=1)
    r1 = start_round(db, sess.id, "aptitude")
    r2 = start_round(db, sess.id, "aptitude")

    assert r1.id == r2.id
    assert db.query(AssessmentRound).filter(
        AssessmentRound.session_id == sess.id
    ).count() == 1


# ── 3. First round activation ─────────────────────────────────────────

def test_round_order_list_has_aptitude_first(db):
    """The first round in ROUND_ORDER is aptitude. ROUND_ORDER is preserved for sequential mode; Practice no longer requires aptitude first."""
    assert ROUND_ORDER[0] == "aptitude"


def test_active_round_is_returned_for_active_session(db):
    """get_active_round returns the active aptitude round."""
    sess = create_session(db, user_id=1)
    r = start_round(db, sess.id, "aptitude")

    active = get_active_round(db, sess.id)
    assert active is not None
    assert active.id == r.id


# ── 4. Round completion ───────────────────────────────────────────────

def test_complete_round_marks_status(db):
    """Completing a round sets status=completed and completed_at."""
    sess = create_session(db, user_id=1)
    r = start_round(db, sess.id, "aptitude")

    completed = complete_round(db, r.id, user_id=1)
    assert completed.status == "completed"
    assert completed.completed_at is not None


def test_complete_round_is_idempotent(db):
    """Completing an already-completed round is safe; completed_at unchanged."""
    sess = create_session(db, user_id=1)
    r = start_round(db, sess.id, "aptitude")

    first = complete_round(db, r.id, user_id=1)
    second = complete_round(db, r.id, user_id=1)

    assert first.id == second.id
    assert first.completed_at == second.completed_at


# ── 5. Next-round progression ─────────────────────────────────────────

def test_sequential_round_order_progression(db):
    """_next_round_type returns correct ordering. ROUND_ORDER is preserved for sequential mode."""
    assert _next_round_type("aptitude") == "coding"
    assert _next_round_type("coding") == "interview"
    assert _next_round_type("interview") is None


def test_aptitude_to_coding_progression(db):
    """After aptitude completes, coding round can be activated."""
    sess = create_session(db, user_id=1)
    apt = start_round(db, sess.id, "aptitude")
    complete_round(db, apt.id, user_id=1)

    coding = start_round(db, sess.id, "coding")
    assert coding.round_type == "coding"
    assert coding.status == "active"


def test_advance_to_next_round_service(db):
    """advance_to_next_round completes current and creates next."""
    sess = create_session(db, user_id=1)
    start_round(db, sess.id, "aptitude")

    coding = advance_to_next_round(db, sess.id, "coding")
    assert coding.round_type == "coding"
    assert coding.status == "active"

    # Aptitude is now completed.
    apt = db.query(AssessmentRound).filter(
        AssessmentRound.session_id == sess.id,
        AssessmentRound.round_type == "aptitude",
    ).first()
    assert apt.status == "completed"


def test_advance_is_idempotent(db):
    """Calling advance_to_next_round twice returns the same next round."""
    sess = create_session(db, user_id=1)
    start_round(db, sess.id, "aptitude")

    first = advance_to_next_round(db, sess.id, "coding")
    second = advance_to_next_round(db, sess.id, "coding")
    assert first.id == second.id

    assert db.query(AssessmentRound).filter(
        AssessmentRound.session_id == sess.id,
        AssessmentRound.status == "active",
    ).count() == 1


# ── 6. Invalid round progression ─────────────────────────────────────

def test_cannot_start_another_round_while_one_is_active(db):
    """Starting a different round type while one is active raises ValueError."""
    sess = create_session(db, user_id=1)
    start_round(db, sess.id, "aptitude")

    with pytest.raises(ValueError, match="already active"):
        start_round(db, sess.id, "coding")


def test_cannot_advance_completed_session(db):
    """advance_to_next_round on a completed session raises ValueError."""
    sess = create_session(db, user_id=1)
    apt = start_round(db, sess.id, "aptitude")
    complete_round(db, apt.id)
    complete_session(db, sess.id)

    with pytest.raises(ValueError):
        advance_to_next_round(db, sess.id, "coding")


# ── 7. Session completion ─────────────────────────────────────────────

def test_session_completes_after_all_rounds(db):
    """Session is marked completed after interview round completes."""
    sess = create_session(db, user_id=1)

    apt = start_round(db, sess.id, "aptitude")
    complete_round(db, apt.id, user_id=1)

    cod = start_round(db, sess.id, "coding")
    complete_round(db, cod.id, user_id=1)

    itr = start_round(db, sess.id, "interview")
    complete_round(db, itr.id, user_id=1)

    completed_sess = complete_session(db, sess.id, user_id=1)
    assert completed_sess.status == "completed"
    assert completed_sess.completed_at is not None


def test_complete_session_is_idempotent(db):
    """Completing an already-completed session is safe."""
    sess = create_session(db, user_id=1)
    apt = start_round(db, sess.id, "aptitude")
    complete_round(db, apt.id)
    complete_session(db, sess.id)

    second = complete_session(db, sess.id)
    assert second.status == "completed"


def test_session_score_finalized(db):
    """_finalize_session_score sets total_score to mean of completed round scores."""
    sess = create_session(db, user_id=1)

    apt = start_round(db, sess.id, "aptitude")
    apt.score = 0.8
    db.commit()
    complete_round(db, apt.id, user_id=1)

    cod = start_round(db, sess.id, "coding")
    cod.score = 0.6
    db.commit()
    complete_round(db, cod.id, user_id=1)

    itr = start_round(db, sess.id, "interview")
    itr.score = 0.7
    db.commit()
    complete_round(db, itr.id, user_id=1)

    _finalize_session_score(db, sess.id)
    db.refresh(sess)

    assert abs(sess.total_score - (0.8 + 0.6 + 0.7) / 3) < 0.001


# ── 8. Multiple practice attempts ─────────────────────────────────────

def test_multiple_practice_attempts_are_separate(db):
    """Two completed practice sessions are persisted independently."""
    # Attempt 1
    sess1 = create_session(db, user_id=1)
    apt1 = start_round(db, sess1.id, "aptitude")
    complete_round(db, apt1.id)
    complete_session(db, sess1.id)

    # Attempt 2 — should create a new session since attempt 1 is completed.
    sess2 = create_session(db, user_id=1)
    assert sess2.id != sess1.id

    sessions = db.query(AssessmentSession).filter(
        AssessmentSession.user_id == 1
    ).all()
    assert len(sessions) == 2

    statuses = {s.status for s in sessions}
    assert "completed" in statuses
    assert "in_progress" in statuses


def test_completed_attempts_are_not_overwritten(db):
    """Completed sessions keep their original completed_at after new attempt starts."""
    sess1 = create_session(db, user_id=1)
    apt1 = start_round(db, sess1.id, "aptitude")
    complete_round(db, apt1.id)
    complete_session(db, sess1.id)
    original_completed_at = sess1.completed_at

    # Start new attempt.
    _sess2 = create_session(db, user_id=1)

    db.refresh(sess1)
    assert sess1.completed_at == original_completed_at


# ── 9. Resume / reconnect ─────────────────────────────────────────────

def test_reconnect_returns_existing_session(db):
    """get_active_session returns same session on reconnect."""
    sess = create_session(db, user_id=1)
    start_round(db, sess.id, "aptitude")

    reconnected = get_active_session(db, user_id=1)
    assert reconnected is not None
    assert reconnected.id == sess.id


def test_reconnect_finds_active_round(db):
    """After reconnect, active round is still accessible."""
    sess = create_session(db, user_id=1)
    r = start_round(db, sess.id, "aptitude")

    # Simulate reconnect — new DB query.
    reconnected_session = get_active_session(db, user_id=1)
    active = get_active_round(db, reconnected_session.id)
    assert active is not None
    assert active.id == r.id


# ── 10. Expiration ────────────────────────────────────────────────────

def test_expired_round_cannot_be_completed(db):
    """Completing an expired round raises ValueError."""
    sess = create_session(db, user_id=1)
    r = start_round(db, sess.id, "aptitude")
    r.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()

    expired = expire_round(db, r.id, user_id=1)
    assert expired.status == "expired"

    with pytest.raises(ValueError, match="expired"):
        complete_round(db, r.id, user_id=1)


def test_expired_session_cannot_start_new_round(db):
    """start_round on an expired session raises ValueError."""
    sess = create_session(db, user_id=1)
    apt = start_round(db, sess.id, "aptitude")
    complete_round(db, apt.id)
    expire_session(db, sess.id)

    with pytest.raises(ValueError):
        start_round(db, sess.id, "coding")


def test_stale_session_is_expired_by_backend(db):
    """Backend expires sessions past their expires_at before returning them."""
    sess = create_session(db, user_id=1)
    # Force expiry in the past.
    sess.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()

    active = get_active_session(db, user_id=1)
    assert active is None

    db.refresh(sess)
    assert sess.status == "expired"


def test_stale_round_is_expired_by_backend(db):
    """Backend expires rounds past their expires_at before returning them."""
    sess = create_session(db, user_id=1)
    r = start_round(db, sess.id, "aptitude")
    r.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()

    active = get_active_round(db, sess.id)
    assert active is None

    db.refresh(r)
    assert r.status == "expired"


# ── 11. Session ownership ─────────────────────────────────────────────

def test_session_ownership_cross_user(db):
    """User 2 cannot access User 1's session."""
    sess = create_session(db, user_id=1)
    assert get_owned_session(db, sess.id, user_id=1) is not None
    assert get_owned_session(db, sess.id, user_id=2) is None


def test_complete_session_rejects_wrong_user(db):
    """complete_session with wrong user_id returns None (no mutation)."""
    sess = create_session(db, user_id=1)
    start_round(db, sess.id, "aptitude")

    result = complete_session(db, sess.id, user_id=2)
    assert result is None

    db.refresh(sess)
    assert sess.status == "in_progress"


# ── 12. Round ownership ───────────────────────────────────────────────

def test_round_ownership_cross_user(db):
    """User 2 cannot access User 1's round."""
    sess = create_session(db, user_id=1)
    r = start_round(db, sess.id, "aptitude")

    assert get_owned_round(db, r.id, user_id=1) is not None
    assert get_owned_round(db, r.id, user_id=2) is None


def test_complete_round_rejects_wrong_user(db):
    """complete_round with wrong user_id returns None (no mutation)."""
    sess = create_session(db, user_id=1)
    r = start_round(db, sess.id, "aptitude")

    result = complete_round(db, r.id, user_id=2)
    assert result is None

    db.refresh(r)
    assert r.status == "active"


# ── 13. Golden-path end-to-end lifecycle ─────────────────────────────

def test_sequential_lifecycle_three_rounds(db):
    """
    Proves the complete sequential assessment lifecycle:

    1.  Authenticated student (user_id=1) starts a practice assessment.
    2.  One AssessmentSession is created.
    3.  First round (aptitude) is created and activated.
    4.  Aptitude round is completed.
    5.  Backend advances to coding round.
    6.  Coding round is activated.
    7.  Coding round is completed.
    8.  Backend advances to interview round.
    9.  Interview round is activated.
    10. Interview round is completed.
    11. AssessmentSession becomes completed.
    12. All rounds are persisted with correct terminal status.
    """
    # Step 1 — Start.
    sess = create_session(db, user_id=1)
    assert sess.status == "in_progress"

    # Step 2 — One session.
    assert db.query(AssessmentSession).filter(AssessmentSession.user_id == 1).count() == 1

    # Step 3 — First round: aptitude.
    apt = start_round(db, sess.id, "aptitude")
    assert apt.round_type == "aptitude"
    assert apt.status == "active"
    assert apt.expires_at is not None

    # Step 4 — Complete aptitude.
    apt = complete_round(db, apt.id, user_id=1)
    assert apt.status == "completed"

    # Step 5/6 — Advance to coding.
    coding = start_round(db, sess.id, "coding")
    assert coding.round_type == "coding"
    assert coding.status == "active"

    # Step 7 — Complete coding.
    coding = complete_round(db, coding.id, user_id=1)
    assert coding.status == "completed"

    # Step 8/9 — Advance to interview.
    interview = start_round(db, sess.id, "interview")
    assert interview.round_type == "interview"
    assert interview.status == "active"

    # Step 10 — Complete interview.
    interview = complete_round(db, interview.id, user_id=1)
    assert interview.status == "completed"

    # Step 11 — Complete session.
    completed_sess = complete_session(db, sess.id, user_id=1)
    assert completed_sess.status == "completed"
    assert completed_sess.completed_at is not None

    # Step 12 — All rounds persisted with correct terminal status.
    rounds = (
        db.query(AssessmentRound)
        .filter(AssessmentRound.session_id == sess.id)
        .all()
    )
    assert len(rounds) == 3
    for r in rounds:
        assert r.status == "completed", f"Round {r.round_type} has status {r.status}"
        assert r.completed_at is not None

    round_types = {r.round_type for r in rounds}
    assert round_types == {"aptitude", "coding", "interview"}
