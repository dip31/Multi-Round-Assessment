"""
Pydantic schemas for aptitude round request/response payloads.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Request schemas ───────────────────────────────────────────────────

class AptitudeAttemptRequest(BaseModel):
    """Payload for submitting an answer to an aptitude question."""

    question_id: int = Field(..., gt=0, examples=[1])
    selected_option: str = Field(..., pattern="^[A-D]$", examples=["A"])
    response_time: Optional[float] = Field(None, ge=0, examples=[15.5])


# ── Response schemas ──────────────────────────────────────────────────

class AptitudeQuestionResponse(BaseModel):
    """Public representation of an aptitude question (without correct answer)."""

    id: int
    question_text: str
    option_a: str
    option_b: str
    option_c: str
    option_d: str
    difficulty: str
    topic_id: Optional[int] = None

    model_config = {"from_attributes": True}


class AptitudeAttemptResponse(BaseModel):
    """Response after submitting an answer."""

    attempt_id: int
    is_correct: bool
    correct_option: str
    reward: Optional[float] = None
    next_difficulty: Optional[str] = None


class AptitudeResultResponse(BaseModel):
    """Round analytics and performance metrics."""

    round_id: int
    total_questions: int
    correct_answers: int
    accuracy: float
    avg_response_time: Optional[float] = None
    score: float
    difficulty_progression: Optional[list] = None

    model_config = {"from_attributes": True}


class AptitudeTopicResponse(BaseModel):
    """Public representation of an aptitude topic."""

    id: int
    name: str

    model_config = {"from_attributes": True}
