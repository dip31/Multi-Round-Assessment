"""Focused service-level coverage for the M2-A lifecycle contract."""

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
    get_owned_round,
    get_owned_session,
    start_round,
)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine, tables=[
        User.__table__,
        AssessmentSession.__table__,
        AssessmentRound.__table__,
    ])
    session = sessionmaker(bind=engine)()
    session.add(User(name="Student", email="student@test.local", password_hash="hash"))
    session.commit()
    try:
        yield session
    finally:
        session.close()


def test_session_and_round_start_are_idempotent(db):
    first = create_session(db, 1)
    second = create_session(db, 1)
    assert first.id == second.id

    first_round = start_round(db, first.id, "aptitude")
    second_round = create_round(db, first.id, "aptitude")
    assert first_round.id == second_round.id
    assert db.query(AssessmentSession).count() == 1
    assert db.query(AssessmentRound).count() == 1


def test_completion_is_idempotent_and_invalid_states_are_rejected(db):
    session = create_session(db, 1)
    assessment_round = create_round(db, session.id, "aptitude")

    completed_round = complete_round(db, assessment_round.id, 1)
    completed_again = complete_round(db, assessment_round.id, 1)
    assert completed_again.id == completed_round.id
    assert completed_again.completed_at == completed_round.completed_at

    completed_session = complete_session(db, session.id, 1)
    completed_again = complete_session(db, session.id, 1)
    assert completed_again.id == completed_session.id
    assert completed_again.completed_at == completed_session.completed_at

    with pytest.raises(ValueError, match="completed"):
        start_round(db, session.id, "coding")


def test_expiration_is_backend_authoritative(db):
    session = create_session(db, 1)
    assessment_round = create_round(db, session.id, "aptitude")
    assessment_round.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()

    assert get_owned_round(db, assessment_round.id, 1).status == "active"
    expired = expire_round(db, assessment_round.id, 1)
    assert expired.status == "expired"
    assert get_owned_session(db, session.id, 1).status == "in_progress"


def test_ownership_prevents_cross_user_access(db):
    db.add(User(name="Other", email="other@test.local", password_hash="hash"))
    db.commit()
    session = create_session(db, 1)
    assessment_round = create_round(db, session.id, "aptitude")

    assert get_owned_session(db, session.id, 2) is None
    assert get_owned_round(db, assessment_round.id, 2) is None
    assert complete_round(db, assessment_round.id, 2) is None


def test_advance_completes_once_and_creates_one_next_round(db):
    session = create_session(db, 1)
    create_round(db, session.id, "aptitude")

    next_round = advance_to_next_round(db, session.id, "coding")
    repeated = advance_to_next_round(db, session.id, "coding")

    assert next_round.id == repeated.id
    assert db.query(AssessmentRound).filter(
        AssessmentRound.session_id == session.id,
        AssessmentRound.status == "active",
    ).count() == 1
