"""
Canonical Transcript Event Format and Normalization for EDI5.

Defines the unified transcript event structure used across:
- Custom LLM WebSocket (edi5_core mode)
- Retell Webhooks (retell_hosted mode)
- Frontend WebSocket streaming
- Database persistence
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
from enum import Enum

try:
    from pydantic import BaseModel
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    BaseModel = object  # type: ignore


class TranscriptSpeaker(str, Enum):
    """Speaker roles in the interview transcript."""
    AI = "ai"
    CANDIDATE = "candidate"
    SYSTEM = "system"


class TranscriptMessageType(str, Enum):
    """Message types for transcript entries."""
    QUESTION = "question"
    ANSWER = "answer"
    FOLLOW_UP = "follow_up"
    SYSTEM = "system"


def _to_dict(obj: Any) -> Dict[str, Any]:
    """
    Safely convert an object to a dictionary.
    
    Handles:
    - Pydantic models (via model_dump())
    - Objects with __dict__ (fallback)
    - Dictionaries (pass through)
    - None (returns empty dict)
    """
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if PYDANTIC_AVAILABLE and isinstance(obj, BaseModel):
        try:
            # Pydantic v2
            return obj.model_dump()
        except AttributeError:
            try:
                # Pydantic v1
                return obj.dict()
            except AttributeError:
                pass
    # Fallback for objects with __dict__
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    # Last resort: try to iterate as dict-like
    try:
        return dict(obj)
    except (TypeError, ValueError):
        return {}


@dataclass(frozen=True)
class CanonicalTranscriptEvent:
    """
    Canonical transcript event for EDI5.
    
    This is the single source of truth for transcript data across all transport layers.
    """
    # Unique identifier for this transcript turn
    turn_id: str
    
    # Speaker: "ai" | "candidate" | "system"
    speaker: str
    
    # The transcript text
    text: str
    
    # Unix timestamp (milliseconds) when this utterance started
    timestamp: int
    
    # Whether this is the final version of this turn
    is_final: bool
    
    # Sequence number for ordering within the interview
    sequence: int
    
    # Optional: Retell's original utterance ID for deduplication
    retell_utterance_id: Optional[str] = None
    
    # Optional: Confidence score from STT (0.0 - 1.0)
    confidence: Optional[float] = None
    
    # Optional: Message type classification
    message_type: Optional[str] = None
    
    # Optional: Turn ID from InterviewTurn table for question-answer mapping
    interview_turn_id: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Remove None values for cleaner JSON
        return {k: v for k, v in data.items() if v is not None}
    
    def to_frontend_dict(self) -> Dict[str, Any]:
        """Convert to frontend-friendly dictionary.

        ``message_type`` is included because the transcript panel renders it as
        the per-utterance label (QUESTION / ANSWER); without it the frontend
        fell back to inferring the label from the speaker.
        """
        return {
            "turn_id": self.turn_id,
            "speaker": self.speaker,
            "text": self.text,
            "timestamp": self.timestamp,
            "is_final": self.is_final,
            "sequence": self.sequence,
            "message_type": self.message_type,
        }


def normalize_retell_utterance(
    utterance: Any,
    sequence: int,
    interview_turn_id: Optional[int] = None,
) -> CanonicalTranscriptEvent:
    """
    Normalize a single Retell utterance to canonical format.
    
    Retell utterance format:
    {
        "role": "agent" | "user",
        "content": "text",
        "utterance_id": "uuid",
        "is_final": true,
        "confidence": 0.95,
        "start_timestamp": 1234567890,
        "end_timestamp": 1234567895
    }
    
    Also handles Pydantic models (Retell SDK v6+) by converting to dict first.
    """
    u = _to_dict(utterance)
    role = u.get("role", "").lower()
    content = u.get("content", "").strip()
    utterance_id = u.get("utterance_id") or u.get("id")
    is_final = u.get("is_final", True)
    confidence = u.get("confidence")
    start_ts = u.get("start_timestamp")
    
    # Map Retell role to canonical speaker
    if role == "agent":
        speaker = TranscriptSpeaker.AI
        message_type = TranscriptMessageType.QUESTION
    elif role == "user":
        speaker = TranscriptSpeaker.CANDIDATE
        message_type = TranscriptMessageType.ANSWER
    else:
        speaker = TranscriptSpeaker.SYSTEM
        message_type = TranscriptMessageType.SYSTEM
    
    # Stable identity for this utterance.
    #
    # This MUST be deterministic for a given utterance position. Retell's
    # Custom LLM protocol (edi5_core mode) sends the *entire* conversation
    # array on every ``update_only`` message — many times per second as STT
    # firms up — and those utterances carry no ``utterance_id``. A random
    # component here therefore minted a brand-new turn_id for the same
    # utterance on every message, so the frontend (which de-duplicates on
    # turn_id) appended the whole conversation again each time instead of
    # updating in place. ``sequence`` is derived from the utterance's index in
    # the array and is stable across rebroadcasts, which makes it the right
    # fallback identity.
    turn_id = utterance_id or f"turn-{sequence}"
    
    # Use start_timestamp if available, otherwise current time
    timestamp = start_ts if start_ts else int(time.time() * 1000)
    
    return CanonicalTranscriptEvent(
        turn_id=turn_id,
        speaker=speaker.value,
        text=content,
        timestamp=timestamp,
        is_final=is_final,
        sequence=sequence,
        retell_utterance_id=utterance_id,
        confidence=confidence,
        message_type=message_type.value,
        interview_turn_id=interview_turn_id,
    )


def normalize_retell_transcript(
    transcript: List[Any],
    base_sequence: int = 0,
    interview_turn_id: Optional[int] = None,
) -> List[CanonicalTranscriptEvent]:
    """
    Normalize a full Retell transcript array to canonical events.
    
    Args:
        transcript: List of Retell utterance objects (dicts or Pydantic models)
        base_sequence: Starting sequence number (for continuing conversations)
        interview_turn_id: Current active InterviewTurn ID for mapping
     
    Returns:
        List of CanonicalTranscriptEvent in order
    """
    if not transcript:
        return []
        
    events = []
    for idx, utterance in enumerate(transcript):
        u = _to_dict(utterance)
        if not u.get("content", "").strip():
            continue
        sequence = base_sequence + idx + 1
        event = normalize_retell_utterance(u, sequence, interview_turn_id)
        events.append(event)
    return events


def extract_utterances(transcript_object: Any) -> List[Dict[str, Any]]:
    """Pull the utterance list out of Retell's ``transcript_object``.

    Retell's REST payloads deliver ``transcript_object`` as a bare JSON array
    of utterances, while some SDK versions and our own fixtures wrap it as
    ``{"utterances": [...]}``. Callers previously assumed the dict shape and
    called ``.get("utterances")`` unguarded, which raises ``AttributeError`` on
    a list and took the whole webhook down with it — so no live transcript
    reached the frontend in retell_hosted mode.

    Accepts either shape and returns ``[]`` for anything unusable.
    
    Also handles Pydantic models (Retell SDK v6+) by converting to dict.
    """
    if not transcript_object:
        return []
    
    # Convert to list of dicts if needed
    if isinstance(transcript_object, list):
        return [_to_dict(u) for u in transcript_object if u is not None]
    if isinstance(transcript_object, dict):
        utterances = transcript_object.get("utterances")
        if isinstance(utterances, list):
            return [_to_dict(u) for u in utterances if u is not None]
        if "role" in transcript_object and ("content" in transcript_object or "text" in transcript_object):
            return [_to_dict(transcript_object)]
    if hasattr(transcript_object, "utterances"):
        utts = getattr(transcript_object, "utterances")
        if isinstance(utts, list):
            return [_to_dict(u) for u in utts if u is not None]
    d = _to_dict(transcript_object)
    if "role" in d and ("content" in d or "text" in d):
        return [d]
    return []


def select_changed_events(
    fingerprints: Dict[str, Any],
    events: List[CanonicalTranscriptEvent],
) -> List[CanonicalTranscriptEvent]:
    """Filter ``events`` down to those whose content actually changed.

    Retell resends the full conversation on every transcript update, so without
    this the backend rebroadcasts every past utterance on every partial STT
    result. Deterministic turn_ids mean the frontend renders that correctly, but
    it is still O(conversation) frames per update; this makes it O(changed).

    ``fingerprints`` is mutated in place and must be scoped to a single call so
    it dies with the connection.
    """
    changed = []
    for event in events:
        fingerprint = (event.text, event.is_final)
        if fingerprints.get(event.turn_id) == fingerprint:
            continue
        fingerprints[event.turn_id] = fingerprint
        changed.append(event)
    return changed


def create_transcript_event_from_text(
    speaker: TranscriptSpeaker,
    text: str,
    turn_id: Optional[str] = None,
    sequence: int = 0,
    is_final: bool = True,
    interview_turn_id: Optional[int] = None,
) -> CanonicalTranscriptEvent:
    """Create a canonical transcript event from plain text (for system messages, etc.)."""
    return CanonicalTranscriptEvent(
        turn_id=turn_id or f"turn-{sequence}-{uuid.uuid4().hex[:8]}",
        speaker=speaker.value,
        text=text.strip(),
        timestamp=int(time.time() * 1000),
        is_final=is_final,
        sequence=sequence,
        message_type=TranscriptMessageType.SYSTEM.value if speaker == TranscriptSpeaker.SYSTEM else (
            TranscriptMessageType.QUESTION.value if speaker == TranscriptSpeaker.AI else TranscriptMessageType.ANSWER.value
        ),
        interview_turn_id=interview_turn_id,
    )


def merge_transcript_events(
    existing: List[CanonicalTranscriptEvent],
    incoming: List[CanonicalTranscriptEvent],
) -> List[CanonicalTranscriptEvent]:
    """
    Merge incoming transcript events with existing ones, handling partial->final updates.
    
    Uses retell_utterance_id for deduplication when available, otherwise falls back
    to turn_id and sequence matching.
    """
    # Build lookup for existing events
    existing_by_id = {}
    existing_by_seq = {}
    
    for event in existing:
        if event.retell_utterance_id:
            existing_by_id[event.retell_utterance_id] = event
        existing_by_seq[event.sequence] = event
    
    merged = []
    used_existing = set()
    
    for inc_event in incoming:
        matched = None
        
        # Try to match by retell_utterance_id first
        if inc_event.retell_utterance_id and inc_event.retell_utterance_id in existing_by_id:
            matched = existing_by_id[inc_event.retell_utterance_id]
            used_existing.add(inc_event.retell_utterance_id)
        # Fallback to sequence matching
        elif inc_event.sequence in existing_by_seq:
            matched = existing_by_seq[inc_event.sequence]
            used_existing.add(inc_event.sequence)
        
        if matched:
            # Update existing event with incoming data
            # Preserve the original turn_id and timestamp
            merged_event = CanonicalTranscriptEvent(
                turn_id=matched.turn_id,
                speaker=matched.speaker,
                text=inc_event.text or matched.text,
                timestamp=matched.timestamp,
                is_final=inc_event.is_final,
                sequence=matched.sequence,
                retell_utterance_id=inc_event.retell_utterance_id or matched.retell_utterance_id,
                confidence=inc_event.confidence or matched.confidence,
                message_type=inc_event.message_type or matched.message_type,
                interview_turn_id=inc_event.interview_turn_id or matched.interview_turn_id,
            )
            merged.append(merged_event)
        else:
            # New event
            merged.append(inc_event)
    
    # Add any existing events that weren't matched (shouldn't happen in normal flow)
    for event in existing:
        key = event.retell_utterance_id or event.sequence
        if key not in used_existing:
            merged.append(event)
    
    # Sort by sequence
    merged.sort(key=lambda e: e.sequence)
    return merged


def normalize_call_transcript_object(
    transcript_object: Any,
    base_sequence: int = 0,
    interview_turn_id: Optional[int] = None,
) -> List[CanonicalTranscriptEvent]:
    """
    Normalize Retell's final call transcript_object to canonical events.

    The final transcript_object from call.retrieve() has format:
    [
        {
            "role": "agent" | "user" | "transfer_target",
            "content": "text",
            "words": [...]
        },
        ...
    ]

    Unlike live updates, this is the authoritative final transcript with no
    utterance_id or is_final fields. Sequence is determined by array order.
    
    Handles lists, wrapped dicts, and Pydantic models (Retell SDK v6+).
    """
    if not transcript_object:
        return []

    utterances = extract_utterances(transcript_object)
    if not utterances:
        return []

    events = []
    for idx, u in enumerate(utterances):
        role = u.get("role", "").lower()
        content = u.get("content", "").strip()
        if not content:
            continue

        if role == "agent":
            speaker = TranscriptSpeaker.AI
            message_type = TranscriptMessageType.QUESTION
        elif role == "user":
            speaker = TranscriptSpeaker.CANDIDATE
            message_type = TranscriptMessageType.ANSWER
        else:
            speaker = TranscriptSpeaker.SYSTEM
            message_type = TranscriptMessageType.SYSTEM

        sequence = base_sequence + idx + 1
        # Stable identity for final transcript: use sequence-based turn_id
        turn_id = f"final-{sequence}"

        event = CanonicalTranscriptEvent(
            turn_id=turn_id,
            speaker=speaker.value,
            text=content,
            timestamp=0,  # Final transcript uses relative timing; wall-time unknown
            is_final=True,
            sequence=sequence,
            retell_utterance_id=u.get("utterance_id") or u.get("id"),
            confidence=u.get("confidence"),
            message_type=message_type.value,
            interview_turn_id=interview_turn_id,
        )
        events.append(event)

    return events