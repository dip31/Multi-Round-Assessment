"""
Pydantic schemas for assessment context and policy.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ── Policy Schemas ────────────────────────────────────────────────────

class PolicyBase(BaseModel):
    """Base policy fields."""
    name: str
    session_duration_minutes: int = 180
    round_duration_minutes: int = 30
    max_attempts: Optional[int] = None  # None = unlimited
    resume_allowed: bool = True
    exit_allowed: bool = True
    progression_mode: str = Field(
        default="sequential",
        pattern="^(independent|sequential)$",
    )
    progression_config: dict = {}


class PolicyCreate(PolicyBase):
    """Create a new policy."""
    pass


class PolicyResponse(PolicyBase):
    """Public policy representation."""
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Context Schemas ───────────────────────────────────────────────────

class ContextBase(BaseModel):
    """Base context fields."""
    mode: str = Field(
        ...,
        pattern="^(practice|portfolio_verification|mock_drive)$",
        examples=["practice"],
    )
    purpose: Optional[str] = None
    company_name: Optional[str] = None
    target_role: Optional[str] = None
    jd_text: Optional[str] = None
    availability_start: Optional[datetime] = None
    availability_end: Optional[datetime] = None


class ContextCreate(ContextBase):
    """Create a new assessment context."""
    policy_id: int
    student_id: Optional[int] = None
    created_by_id: Optional[int] = None


class ContextResponse(ContextBase):
    """Public context representation."""
    id: int
    policy_id: int
    policy: PolicyResponse
    student_id: Optional[int] = None
    created_by_id: Optional[int] = None
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ContextWithSessionsResponse(ContextResponse):
    """Context with associated sessions."""
    session_count: int = 0
    completed_sessions: int = 0

    model_config = {"from_attributes": True}
