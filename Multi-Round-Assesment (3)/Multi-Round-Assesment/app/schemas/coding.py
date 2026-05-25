"""
Pydantic schemas for coding round request/response payloads.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Request schemas ───────────────────────────────────────────────────

class CodingSubmissionRequest(BaseModel):
    """Payload for submitting code for execution."""

    problem_id: int = Field(..., gt=0, examples=[1])
    code: str = Field(..., min_length=1, examples=["def solution(n):\n    return n * 2"])
    language: str = Field(..., examples=["python"])


# ── Response schemas ──────────────────────────────────────────────────

class CodingTestCaseResponse(BaseModel):
    """Public representation of a test case (hidden cases excluded)."""

    id: int
    input_data: str
    expected_output: str
    is_hidden: bool
    explanation: Optional[str] = None

    model_config = {"from_attributes": True}


class CodingProblemResponse(BaseModel):
    """Public representation of a coding problem."""

    id: int
    title: str
    description: str
    difficulty: Optional[str] = None
    tags: Optional[List[str]] = None
    input_format: Optional[str] = None
    output_format: Optional[str] = None
    constraints: Optional[str] = None
    test_cases: List[CodingTestCaseResponse] = []

    model_config = {"from_attributes": True}


class CodingSubmissionResponse(BaseModel):
    """Response after code submission."""

    submission_id: int
    judge0_token: Optional[str] = None
    status: str
    score: Optional[float] = None
    execution_time: Optional[float] = None
    memory_used: Optional[int] = None
    submitted_at: datetime

    model_config = {"from_attributes": True}


class CodingSubmissionStatusResponse(BaseModel):
    """Detailed status of a code submission."""

    submission_id: int
    problem_id: int
    status: str
    score: Optional[float] = None
    execution_time: Optional[float] = None
    memory_used: Optional[int] = None
    test_cases_passed: Optional[int] = None
    total_test_cases: Optional[int] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}
