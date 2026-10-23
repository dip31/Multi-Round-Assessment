"""Test webhook handler with Pydantic TranscriptObject models."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database.base import Base
from app.models.user import User
from app.models.assessment import AssessmentSession, AssessmentRound
from app.models.assessment_context import AssessmentPolicy, AssessmentContext
from app.models.interview import (
    InterviewSession,
    InterviewConversation,
    InterviewMessage,
    InterviewMessageSpeaker,
    InterviewMessageType,
    InterviewTurn,
)

# Mock TranscriptObject from Retell SDK
class MockTranscriptObjectWord(BaseModel):
    end: Optional[float] = None
    start: Optional[float] = None
    word: Optional[str] = None


class MockTranscriptObject(BaseModel):
    content: str
    role: str  # "agent", "user", "transfer_target"
    words: List[Optional[MockTranscriptObjectWord]]


class TestWebhookTranscriptHandling:
    """Test webhook handler with Pydantic TranscriptObject models."""

    @pytest.fixture()
    def db(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine, tables=[
            User.__table__,
            AssessmentPolicy.__table__,
            AssessmentContext.__table__,
            AssessmentSession.__table__,
            AssessmentRound.__table__,
            InterviewSession.__table__,
            InterviewTurn.__table__,
            InterviewConversation.__table__,
            InterviewMessage.__table__,
        ])
        session = sessionmaker(bind=engine)()
        user = User(name="Test User", email="test@test.com", password_hash="hash")
        session.add(user)
        session.commit()
        assessment = AssessmentSession(user_id=user.id, status="active")
        session.add(assessment)
        session.commit()
        round_obj = AssessmentRound(session_id=assessment.id, round_type="interview", status="active")
        session.add(round_obj)
        session.commit()
        yield session
        session.close()

    def create_interview(self, db, user_id, assessment_id, retell_call_id="call-test-123", voice_mode="retell_hosted"):
        interview = InterviewSession(
            session_id=assessment_id,
            round_id=None,
            phase="TECHNICAL",
            current_turn=1,
            total_turns=5,
            retell_call_id=retell_call_id,
            retell_agent_id="agent-test",
            personalization_metadata={"voice_mode": voice_mode},
        )
        db.add(interview)
        db.commit()
        db.refresh(interview)
        return interview

    @pytest.mark.asyncio
    async def test_webhook_persists_pydantic_transcript_object(self, db):
        """Test that webhook can persist transcript_object with Pydantic models."""
        from app.modules.interview.services.transcript_normalizer import extract_utterances, normalize_retell_transcript
        
        # Create mock Pydantic TranscriptObject models (like SDK returns)
        from pydantic import BaseModel
        from typing import List, Optional
        
        class MockTranscriptObjectWord(BaseModel):
            end: Optional[float] = None
            start: Optional[float] = None
            word: Optional[str] = None
        
        class MockTranscriptObject(BaseModel):
            content: str
            role: str
            words: List[Optional[MockTranscriptObjectWord]]
        
        # Create interview
        user = db.query(User).first()
        assessment = db.query(AssessmentSession).first()
        interview = self.create_interview(db, user.id, assessment.id, retell_call_id="call-test-123")
        
        # Create mock Pydantic transcript objects (like SDK returns)
        utterance1 = MockTranscriptObject(
            content="Hello, welcome to the interview.",
            role="agent",
            words=[]
        )
        utterance2 = MockTranscriptObject(
            content="Thank you, happy to be here.",
            role="user",
            words=[]
        )
        
        transcript_object = [utterance1, utterance2]
        
        # Test that extract_utterances works with Pydantic models
        from app.modules.interview.services.transcript_normalizer import extract_utterances, normalize_retell_transcript
        
        utterances = extract_utterances(transcript_object)
        assert len(utterances) == 2
        assert utterances[0]["role"] == "agent"
        assert utterances[0]["content"] == "Hello, welcome to the interview."
        assert utterances[1]["role"] == "user"
        assert utterances[1]["content"] == "Thank you, happy to be here."
        
        # Test that normalize_retell_transcript works with Pydantic models
        canonical_events = normalize_retell_transcript(transcript_object, interview_turn_id=1)
        assert len(canonical_events) == 2
        assert canonical_events[0].speaker == "ai"
        assert canonical_events[1].speaker == "candidate"
        assert canonical_events[0].interview_turn_id == 1
        assert canonical_events[1].interview_turn_id == 1

    @pytest.mark.asyncio
    async def test_normalize_call_transcript_object_with_pydantic(self, db):
        """Test normalize_call_transcript_object with Pydantic models (finalization)."""
        from app.modules.interview.services.transcript_normalizer import normalize_call_transcript_object
        
        from pydantic import BaseModel
        from typing import List, Optional
        
        class MockTranscriptObjectWord(BaseModel):
            end: Optional[float] = None
            start: Optional[float] = None
            word: Optional[str] = None
        
        class MockTranscriptObject(BaseModel):
            content: str
            role: str
            words: List[Optional[MockTranscriptObjectWord]]
        
        utterance1 = MockTranscriptObject(
            content="Hello, welcome to the interview.",
            role="agent",
            words=[]
        )
        utterance2 = MockTranscriptObject(
            content="Thank you, happy to be here.",
            role="user",
            words=[]
        )
        
        transcript_object = [utterance1, utterance2]
        
        from app.modules.interview.services.transcript_normalizer import normalize_call_transcript_object
        
        events = normalize_call_transcript_object(transcript_object, interview_turn_id=1)
        
        assert len(events) == 2
        assert events[0].speaker == "ai"
        assert events[0].text == "Hello, welcome to the interview."
        assert events[1].speaker == "candidate"
        assert events[1].text == "Thank you, happy to be here."
        assert all(e.is_final for e in events)
        assert events[0].sequence == 1
        assert events[1].sequence == 2
        assert all(e.interview_turn_id == 1 for e in events)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])