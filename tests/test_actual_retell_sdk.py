"""Test with actual Retell SDK v6.0.1 types."""

import pytest
from pydantic import BaseModel
from typing import List, Optional

# Test with actual Retell SDK types
from retell.types.web_call_response import TranscriptObject, TranscriptObjectWord, WebCallResponse


class TestActualRetellSDKTypes:
    """Test that our normalization works with actual Retell SDK v6.0.1 types."""

    def test_transcript_object_is_pydantic_model(self):
        """Verify TranscriptObject is a Pydantic model."""
        from pydantic import BaseModel
        assert issubclass(TranscriptObject, BaseModel)

    def test_transcript_object_fields(self):
        """Verify TranscriptObject has expected fields."""
        # Check model fields
        fields = TranscriptObject.model_fields
        assert "content" in fields
        assert "role" in fields
        assert "words" in fields

    def test_transcript_object_word_fields(self):
        """Verify TranscriptObjectWord has expected fields."""
        from pydantic import BaseModel
        assert issubclass(TranscriptObjectWord, BaseModel)
        fields = TranscriptObjectWord.model_fields
        assert "content" in fields or "word" in fields
        assert "start" in fields
        assert "end" in fields

    def test_model_dump_works(self):
        """Test that model_dump() works on TranscriptObject."""
        word = TranscriptObjectWord(start=0.0, end=1.0, word="Hello")
        utterance = TranscriptObject(
            content="Hello world",
            role="agent",
            words=[word]
        )
        
        # model_dump should work
        dumped = utterance.model_dump()
        assert dumped["content"] == "Hello world"
        assert dumped["role"] == "agent"
        assert len(dumped["words"]) == 1
        assert dumped["words"][0]["word"] == "Hello"

    def test_model_dump_exclude_none(self):
        """Test model_dump with exclude_none."""
        utterance = TranscriptObject(
            content="Test",
            role="user",
            words=[]
        )
        dumped = utterance.model_dump(exclude_none=True)
        # words should be present even if empty list
        assert "words" in dumped


if __name__ == "__main__":
    pytest.main([__file__, "-v"])