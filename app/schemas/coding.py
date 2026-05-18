"""
Pydantic Schemas — Coding Round

Request validation and response serialization for all coding endpoints.
"""

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class CodingProblemListResponse(BaseModel):
    """Compact problem info for the problems list endpoint."""
    id: int
    title: str
    difficulty: str
    tags: List[str]
    problem_order: int          # candidate's position in session (1, 2, 3...)
    status: str                 # not_attempted | attempted | accepted
    marked_for_review: bool

    class Config:
        from_attributes = True


class CodingTestCaseResponse(BaseModel):
    """Visible test case shown to candidate (hidden=False only)."""
    id: int
    input_data: str
    expected_output: str
    case_order: int

    class Config:
        from_attributes = True


class CodingProblemDetailResponse(BaseModel):
    """Full problem details including visible test cases."""
    id: int
    title: str
    description: str
    difficulty: str
    tags: List[str]
    input_format: Optional[str]
    output_format: Optional[str]
    constraints: Optional[str]
    visible_test_cases: List[CodingTestCaseResponse]

    class Config:
        from_attributes = True


# ── Run Code (visible test cases only, no DB storage) ─────────────────────────

class RunCodeRequest(BaseModel):
    """Run code against visible test cases only."""
    round_id: int
    problem_id: int
    code: str
    language: str               # "python" | "cpp" | "java"


class RunCodeTestResult(BaseModel):
    input_data: str
    expected_output: str
    actual_output: str
    passed: bool


class RunCodeResponse(BaseModel):
    results: List[RunCodeTestResult]


# ── Submit Code (all test cases, stores result) ───────────────────────────────

class SubmitCodeRequest(BaseModel):
    """Code submission from candidate — evaluated against all test cases."""
    round_id: int
    problem_id: int
    code: str
    language: str               # "python" | "cpp" | "java"


class SubmitCodeResponse(BaseModel):
    """Synchronous verdict returned immediately after evaluation."""
    submission_id: int
    verdict: str                # accepted | partial | wrong_answer |
                                # compilation_error | runtime_error |
                                # time_limit_exceeded
    score: float
    passed_cases: int
    total_cases: int
    execution_time: Optional[float]
    memory_used: Optional[int]

    class Config:
        from_attributes = True


# ── Submission History ────────────────────────────────────────────────────────

class SubmissionHistoryItem(BaseModel):
    submission_id: int
    status: str
    score: float
    submitted_at: datetime

    class Config:
        from_attributes = True


# ── Mark for Review ───────────────────────────────────────────────────────────

class MarkReviewResponse(BaseModel):
    problem_id: int
    marked_for_review: bool
    message: str


# ── Session Lifecycle ─────────────────────────────────────────────────────────

class StartRoundResponse(BaseModel):
    """Response when candidate starts the coding round."""
    round_id: int
    status: str
    time_limit_minutes: int
    end_time: datetime
    problems: List[CodingProblemListResponse]

    class Config:
        from_attributes = True


class SessionStatusResponse(BaseModel):
    """Live session status including countdown timer."""
    round_id: int
    status: str
    time_limit_minutes: int
    end_time: datetime
    time_remaining_seconds: int     # frontend uses this for countdown
    problems: List[CodingProblemListResponse]
    all_problems_solved: bool       # true when all problems have 'accepted' status

    class Config:
        from_attributes = True


class SessionResultResponse(BaseModel):
    """Final result after round ends."""
    round_id: int
    status: str
    total_score: float
    problems_attempted: int
    problems_solved: int

    class Config:
        from_attributes = True
