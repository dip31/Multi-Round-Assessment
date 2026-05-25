"""
Pydantic schemas for assessment session and round payloads.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Request schemas ───────────────────────────────────────────────────

class SessionCreate(BaseModel):
    """Payload to start a new assessment session (user_id comes from auth)."""

    pass  # user_id is injected from the authenticated user


class RoundCreate(BaseModel):
    """Payload to create a new round within a session."""

    round_type: str = Field(
        ...,
        pattern="^(aptitude|coding|interview)$",
        examples=["aptitude"],
    )


# ── Response schemas ──────────────────────────────────────────────────

class RoundResponse(BaseModel):
    """Public representation of an assessment round."""

    id: int
    session_id: int
    round_type: str
    status: str
    score: float
    max_questions: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    """Public representation of an assessment session."""

    id: int
    user_id: int
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_score: float
    time_remaining_seconds: Optional[int] = 1800
    rounds: List[RoundResponse] = []

    model_config = {"from_attributes": True}
