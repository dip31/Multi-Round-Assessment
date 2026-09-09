"""
Pydantic schemas for coding round request/response payloads.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.modules.coding.helpers import serialize_tags


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
    tags: List[str] = Field(default_factory=list)
    input_format: Optional[str] = None
    output_format: Optional[str] = None
    constraints: Optional[str] = None
    test_cases: List[CodingTestCaseResponse] = []

    model_config = {"from_attributes": True}

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, v):
        return serialize_tags(v)


class CodingTestCaseResult(BaseModel):
    """Per-test-case result for /run only (visible cases)."""
    input_data: str
    expected_output: str
    actual_output: str
    passed: bool


class CodingRunResponse(BaseModel):
    """Response from POST /coding/run — stateless, no DB row created."""
    status: str  # accepted | wrong_answer | runtime_error | etc.
    test_cases_passed: int
    total_test_cases: int
    execution_time: Optional[float] = None
    test_case_results: List[CodingTestCaseResult] = []  # visible cases only
    compile_output: Optional[str] = None
    stderr: Optional[str] = None
    message: Optional[str] = None


class CodingSubmissionResponse(BaseModel):
    """Response from POST /coding/submit — persistent, DB row created."""
    submission_id: int  # Required. Never null.
    status: str
    score: float  # 0.0–1.0
    test_cases_passed: int
    total_test_cases: int
    submitted_at: datetime  # Required. Populated from DB after commit.
    execution_time: Optional[float] = None
    compile_output: Optional[str] = None
    stderr: Optional[str] = None
    message: Optional[str] = None

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
    compile_output: Optional[str] = None
    stderr: Optional[str] = None
    message: Optional[str] = None

    model_config = {"from_attributes": True}
