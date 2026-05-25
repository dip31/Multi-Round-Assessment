"""
Pydantic schemas for interview round request / response payloads.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel


# ── Resume Upload ──────────────────────────────────────────────────────
class ResumeUploadResponse(BaseModel):
    """Response after uploading resume and generating question pool."""
    status: str
    pool_id: int
    question_count: int
    pending_approval: bool


# ── Question Pool ──────────────────────────────────────────────────────
class QuestionItem(BaseModel):
    """Single interview question."""
    question: str
    difficulty: str  # EASY, MEDIUM, HARD
    topic: str  # General, Experience, Technical, etc.
    phase: str  # HR, TECHNICAL


class QuestionPoolResponse(BaseModel):
    """Response with question pool details."""
    pool_id: int
    questions: List[QuestionItem]
    approved: bool
    extracted_skills: List[str]


class ApprovePoolRequest(BaseModel):
    """Request to approve or reject a question pool."""
    approved: bool


class ApprovePoolResponse(BaseModel):
    """Response after approval action."""
    status: str  # "approved" or "rejected"


# ── Interview Session ──────────────────────────────────────────────────
class StartInterviewResponse(BaseModel):
    """Response after starting interview session."""
    interview_id: int
    phase: str  # HR or TECHNICAL
    total_turns: int


# ── Next Question ──────────────────────────────────────────────────────
class NextQuestionResponse(BaseModel):
    """Response with next interview question."""
    turn_number: int
    question: str  # Rephrased question text
    question_id: str  # Unique ID to prevent duplicates
    difficulty: str  # EASY, MEDIUM, HARD
    phase: str  # HR or TECHNICAL


# ── Submit Response ────────────────────────────────────────────────────
class BehavioralSnapshot(BaseModel):
    """Behavioral metrics from proctoring."""
    eye_contact_pct: Optional[float] = 0.5
    head_stability: Optional[float] = 0.5


class SubmitResponseRequest(BaseModel):
    """Request to submit interview response."""
    transcript: str
    response_time_sec: float
    behavioral_snapshot: Optional[BehavioralSnapshot] = None


class NextQuestionInfo(BaseModel):
    """Next question details embedded in /respond response."""
    text: str
    difficulty: str  # EASY, MEDIUM, HARD
    phase: str  # HR, TECHNICAL
    turn_number: int


class ScoresInfo(BaseModel):
    """Per-turn scoring breakdown."""
    content_score: float
    intent_score: float
    behavior_score: float
    final_score: float


class InterviewSummaryInfo(BaseModel):
    """Summary stats returned on COMPLETE."""
    total_turns: int
    avg_final_score: float
    followup_rate: float


class SubmitResponseResponse(BaseModel):
    """
    Single response from POST /respond.

    Contains all data the frontend needs — no extra API calls required.
    """
    action: str  # "FOLLOWUP" | "NEXT" | "COMPLETE" | "RETRY"
    message: str  # What interviewer says (spoken via TTS)
    is_complete: bool

    followup_type: Optional[str] = None  # SHORT|PARTIAL|IRRELEVANT|NEGATIVE|null
    next_question: Optional[NextQuestionInfo] = None  # Present only when action == NEXT
    scores: Optional[ScoresInfo] = None  # Null when action == RETRY
    interview_summary: Optional[InterviewSummaryInfo] = None  # Present only when action == COMPLETE


# ── STT (Speech-to-Text) ───────────────────────────────────────────────
class STTResponse(BaseModel):
    """Response from speech-to-text endpoint."""
    transcript: str


# ── TTS (Text-to-Speech) ───────────────────────────────────────────────
class TTSRequest(BaseModel):
    """Request for text-to-speech (passed as query param)."""
    text: str


# ── Interview Report ──────────────────────────────────────────────────
class FollowupItem(BaseModel):
    """A single follow-up turn under a parent main turn."""
    followup_number: int
    question_text: str
    candidate_response: Optional[str] = None
    content_score: Optional[float] = None
    intent: Optional[str] = None
    response_time_sec: Optional[float] = None


class TurnReviewItem(BaseModel):
    """Per-turn review for interview report (main turns only)."""
    turn_number: int
    question_text: str
    difficulty: Optional[str] = None
    candidate_response: Optional[str] = None
    content_score: Optional[float] = None
    intent: Optional[str] = None
    behavior_score: Optional[float] = None
    final_score: Optional[float] = None
    response_time_sec: Optional[float] = None
    rl_reward: Optional[float] = None
    followups: List[FollowupItem] = []


class InterviewReportResponse(BaseModel):
    """Complete interview assessment report."""
    overall_score: float  # 0.0-1.0
    content_score: float  # 0.0-1.0 (avg from main turns)
    behavior_score: float  # 0.0-1.0 (avg from behavioral)
    final_score: float  # 0.0-1.0 (avg final_score from main turns)
    feedback_summary: str
    turn_reviews: List[TurnReviewItem]
    total_turns: int
    followup_rate: float  # percentage
    followup_interpretation: str  # human-readable interpretation
