"""Regression tests for Retell TranscriptObject normalization (SDK v6.0.1)."""

import pytest
from unittest.mock import MagicMock, patch
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# Import the functions to test
from app.modules.interview.services.transcript_normalizer import (
    extract_utterances,
    normalize_call_transcript_object,
    normalize_retell_transcript,
    normalize_retell_utterance,
    CanonicalTranscriptEvent,
    TranscriptSpeaker,
    TranscriptMessageType,
)


class MockTranscriptObjectWord(BaseModel):
    """Mock TranscriptObjectWord from retell SDK."""
    end: Optional[float] = None
    start: Optional[float] = None
    word: Optional[str] = None


class MockTranscriptObject(BaseModel):
    """Mock TranscriptObject from retell SDK v6.0.1."""
    content: str
    role: str  # "agent", "user", "transfer_target"
    words: List[MockTranscriptObjectWord]


class TestTranscriptObjectNormalization:
    """Tests for handling Retell SDK Pydantic TranscriptObject models."""

    def test_extract_utterances_with_pydantic_models(self):
        """extract_utterances should handle Pydantic TranscriptObject models."""
        # Create mock Pydantic models (like SDK returns)
        utterance1 = MockTranscriptObject(
            content="Hello, welcome to the interview.",
            role="agent",
            words=[MockTranscriptObjectWord(start=0.0, end=1.5, word="Hello")]
        )
        utterance2 = MockTranscriptObject(
            content="Thank you, happy to be here.",
            role="user",
            words=[MockTranscriptObjectWord(start=1.5, end=3.0, word="Thank")]
        )
        
        transcript_object = [utterance1, utterance2]
        
        # This should not raise AttributeError
        utterances = extract_utterances(transcript_object)
        
        assert len(utterances) == 2
        assert utterances[0]["role"] == "agent"
        assert utterances[0]["content"] == "Hello, welcome to the interview."
        assert utterances[1]["role"] == "user"
        assert utterances[1]["content"] == "Thank you, happy to be here."

    def test_extract_utterances_with_dicts_still_works(self):
        """extract_utterances should still work with plain dicts (backward compat)."""
        transcript_object = [
            {"role": "agent", "content": "Hello", "utterance_id": "1", "is_final": True},
            {"role": "user", "content": "Hi", "utterance_id": "2", "is_final": True},
        ]
        
        utterances = extract_utterances(transcript_object)
        
        assert len(utterances) == 2
        assert utterances[0]["role"] == "agent"
        assert utterances[1]["role"] == "user"

    def test_extract_utterances_with_wrapped_dict(self):
        """extract_utterances should handle wrapped dict with 'utterances' key."""
        transcript_object = {
            "utterances": [
                {"role": "agent", "content": "Hello"},
                {"role": "user", "content": "Hi"},
            ]
        }
        
        utterances = extract_utterances(transcript_object)
        
        assert len(utterances) == 2

    def test_normalize_call_transcript_object_with_pydantic_models(self):
        """normalize_call_transcript_object should handle Pydantic models."""
        utterance1 = MockTranscriptObject(
            content="Hello, welcome to the interview.",
            role="agent",
            words=[MockTranscriptObjectWord(start=0.0, end=1.5, word="Hello")]
        )
        utterance2 = MockTranscriptObject(
            content="Thank you, happy to be here.",
            role="user",
            words=[MockTranscriptObjectWord(start=1.5, end=3.0, word="Thank")]
        )
        
        transcript_object = [utterance1, utterance2]
        
        # This should not raise AttributeError about .get()
        events = normalize_call_transcript_object(transcript_object)
        
        assert len(events) == 2
        assert events[0].speaker == "ai"
        assert events[0].text == "Hello, welcome to the interview."
        assert events[1].speaker == "candidate"
        assert events[1].text == "Thank you, happy to be here."
        assert all(e.is_final for e in events)
        assert events[0].sequence == 1
        assert events[1].sequence == 2

    def test_normalize_retell_transcript_with_pydantic_models(self):
        """normalize_retell_transcript should handle Pydantic models (for webhook)."""
        utterance1 = MockTranscriptObject(
            content="Hello, welcome to the interview.",
            role="agent",
            words=[]
        )
        utterance2 = MockTranscriptObject(
            content="Thank you.",
            role="user",
            words=[]
        )
        
        transcript_object = [utterance1, utterance2]
        
        # This should not raise AttributeError
        events = normalize_retell_transcript(transcript_object)
        
        assert len(events) == 2
        assert events[0].speaker == "ai"
        assert events[1].speaker == "candidate"

    def test_normalize_retell_utterance_with_pydantic_model(self):
        """normalize_retell_utterance should handle Pydantic model."""
        utterance = MockTranscriptObject(
            content="Test content",
            role="agent",
            words=[]
        )
        
        event = normalize_retell_utterance(utterance, sequence=1)
        
        assert event.speaker == "ai"
        assert event.text == "Test content"
        assert event.sequence == 1

    def test_empty_transcript_object(self):
        """Empty transcript should return empty list."""
        assert extract_utterances([]) == []
        assert normalize_call_transcript_object([]) == []
        assert normalize_retell_transcript([]) == []

    def test_none_transcript_object(self):
        """None transcript should return empty list."""
        assert extract_utterances(None) == []
        assert normalize_call_transcript_object(None) == []
        assert normalize_retell_transcript(None) == []

    def test_transfer_target_role(self):
        """transfer_target role should map to system."""
        utterance = MockTranscriptObject(
            content="Transferring...",
            role="transfer_target",
            words=[]
        )
        
        events = normalize_call_transcript_object([utterance])
        
        assert len(events) == 1
        assert events[0].speaker == "system"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])