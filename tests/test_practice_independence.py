"""
EDI5 M2-E: Practice Independent-Round Semantics Tests.

Covers:
1. Direct starts of MCQ, Coding, Interview
2. Independent completion (no auto-advancement)
3. Conflicting active round (HTTP 409)
4. Same-round resume (success)
5. Repeated attempts (distinct sessions)
6. Cross-user isolation
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import HTTPException

from app.database.base import Base
from app.models.assessment import AssessmentRound, AssessmentSession
from app.models.assessment_context import AssessmentContext, AssessmentPolicy
from app.models.user import User
from app.modules.practice.routers.practice_router import start_practice, PracticeStartRequest, complete_practice_round, CompleteRoundRequest
from app.services.session_service import get_active_round

@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[
            User.__table__, 
            AssessmentContext.__table__,
            AssessmentPolicy.__table__,
            AssessmentSession.__table__, 
            AssessmentRound.__table__
        ],
    )
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    # User 1 — primary student
    session.add(User(name="Alice", email="alice@test.local", password_hash="hash"))
    # User 2 — different student
    session.add(User(name="Bob", email="bob@test.local", password_hash="hash"))
    # Add default practice policy (ID=2)
    policy = AssessmentPolicy(
        id=2,
        name="Default Practice Policy",
        session_duration_minutes=180,
        round_duration_minutes=30,
        max_attempts=None,
        resume_allowed=True,
        exit_allowed=True,
        progression_mode="independent",
        progression_config={}
    )
    session.add(policy)
    
    session.commit()
    try:
        yield session
    finally:
        session.close()

# Helper for current_user
class MockUser:
    def __init__(self, user_id):
        self.id = user_id

def test_start_coding_directly(db):
    """Practice allows direct start of Coding without Aptitude first."""
    user = MockUser(1)
    req = PracticeStartRequest(round_type="coding")
    resp = start_practice(payload=req, db=db, current_user=user)
    
    assert resp.active_round.round_type == "coding"
    assert resp.is_new is True
    
    round_in_db = get_active_round(db, resp.session_id)
    assert round_in_db.round_type == "coding"

def test_start_interview_directly(db):
    """Practice allows direct start of Interview."""
    user = MockUser(1)
    req = PracticeStartRequest(round_type="interview")
    resp = start_practice(payload=req, db=db, current_user=user)
    
    assert resp.active_round.round_type == "interview"

def test_start_aptitude_directly(db):
    """Practice allows direct start of Aptitude."""
    user = MockUser(1)
    req = PracticeStartRequest(round_type="aptitude")
    resp = start_practice(payload=req, db=db, current_user=user)
    
    assert resp.active_round.round_type == "aptitude"

def test_complete_independent_coding_no_auto_advance(db):
    """Completing an independent coding round finishes the session, no interview is created."""
    user = MockUser(1)
    req = PracticeStartRequest(round_type="coding")
    start_resp = start_practice(payload=req, db=db, current_user=user)
    session_id = start_resp.session_id
    
    complete_req = CompleteRoundRequest(round_id=start_resp.active_round.id, round_type="coding")
    complete_resp = complete_practice_round(payload=complete_req, db=db, current_user=user)
    
    assert complete_resp.session_completed is True
    assert complete_resp.next_round is None
    
    # Verify in DB
    rounds = db.query(AssessmentRound).filter(AssessmentRound.session_id == session_id).all()
    assert len(rounds) == 1
    assert rounds[0].round_type == "coding"
    assert rounds[0].status == "completed"
    
    sess = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    assert sess.status == "completed"

def test_conflicting_active_round_returns_409(db):
    """Trying to start Aptitude while Coding is active raises 409."""
    user = MockUser(1)
    req_coding = PracticeStartRequest(round_type="coding")
    start_practice(payload=req_coding, db=db, current_user=user)
    
    req_aptitude = PracticeStartRequest(round_type="aptitude")
    with pytest.raises(HTTPException) as exc:
        start_practice(payload=req_aptitude, db=db, current_user=user)
    
    assert exc.value.status_code == 409
    assert "active coding round is already in progress" in str(exc.value.detail)

def test_same_round_resume(db):
    """Trying to start Coding while Coding is active resumes it."""
    user = MockUser(1)
    req = PracticeStartRequest(round_type="coding")
    resp1 = start_practice(payload=req, db=db, current_user=user)
    
    resp2 = start_practice(payload=req, db=db, current_user=user)
    
    assert resp2.is_new is False
    assert resp1.session_id == resp2.session_id
    assert resp1.active_round.id == resp2.active_round.id

def test_repeated_attempts_are_distinct(db):
    """Completing a practice and starting again creates a distinct attempt."""
    user = MockUser(1)
    req = PracticeStartRequest(round_type="coding")
    
    # Attempt 1
    resp1 = start_practice(payload=req, db=db, current_user=user)
    complete_req = CompleteRoundRequest(round_id=resp1.active_round.id, round_type="coding")
    complete_practice_round(payload=complete_req, db=db, current_user=user)
    
    # Attempt 2
    resp2 = start_practice(payload=req, db=db, current_user=user)
    
    assert resp1.session_id != resp2.session_id
    assert resp2.is_new is True

def test_cross_user_isolation(db):
    """User 2 starting coding does not conflict with User 1's active coding round."""
    user1 = MockUser(1)
    user2 = MockUser(2)
    
    req = PracticeStartRequest(round_type="coding")
    
    resp1 = start_practice(payload=req, db=db, current_user=user1)
    resp2 = start_practice(payload=req, db=db, current_user=user2)
    
    assert resp1.session_id != resp2.session_id
    assert resp1.active_round.id != resp2.active_round.id
