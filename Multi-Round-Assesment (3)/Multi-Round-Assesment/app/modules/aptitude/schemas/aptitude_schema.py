"""
Pydantic schemas for aptitude round request / response payloads.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class NextQuestionResponse(BaseModel):
    """Response containing the next aptitude question."""
    question_id: int
    question_text: str
    options: Dict[str, str]
    difficulty: str


class SubmitAnswerRequest(BaseModel):
    """Request payload for submitting an answer."""
    question_id: int
    selected_option: str
    response_time: float


class SubmitAnswerResponse(BaseModel):
    """Response after submitting an answer (with RL metadata)."""
    correct: bool
    correct_option: str
    reward: Optional[float] = None
    next_difficulty: Optional[str] = None
    next_question: Optional[NextQuestionResponse] = None


class AnswerReviewItem(BaseModel):
    """Per-question answer review for the completed round."""
    attempt_number: int
    question_id: int
    question_text: str
    difficulty: str
    selected_option: Optional[str] = None
    correct_option: str
    is_correct: bool
    response_time: Optional[float] = None
    reward: Optional[float] = None


class RoundResultResponse(BaseModel):
    """Summary statistics for a completed aptitude round."""
    total_questions: int
    correct_answers: int
    accuracy: float
    average_response_time: float
    longest_correct_streak: int
    difficulty_progression: List[str]
    rl_report: List[Dict]
    answer_review: List[AnswerReviewItem]


class DifficultyBucket(BaseModel):
    correct: int
    total: int


class DifficultyStatsResponse(BaseModel):
    easy: DifficultyBucket
    medium: DifficultyBucket
    hard: DifficultyBucket


class ProgressionItem(BaseModel):
    question: int
    difficulty: str
    correct: bool


class ResponseTimeItem(BaseModel):
    question: int
    time: float


class RLSummaryResponse(BaseModel):
    increases: int
    decreases: int
    peak_difficulty: str
    final_difficulty: str


class ProctoringSummaryResponse(BaseModel):
    tab_switch: int
    fullscreen_exit: int
    idle_events: int


class TopicStatResponse(BaseModel):
    topic: str
    correct: int
    total: int
    accuracy: float
    avg_response_time: float


class AptitudeResultResponse(BaseModel):
    score: float
    total_questions: int
    accuracy: float
    avg_response_time: float
    percentile: float
    has_multiple_rounds: bool
    difficulty_stats: DifficultyStatsResponse
    progression: List[ProgressionItem]
    response_times: List[ResponseTimeItem]
    rl_summary: RLSummaryResponse
    proctoring: ProctoringSummaryResponse
    topic_stats: List[TopicStatResponse] = []


RoundResultResponse = AptitudeResultResponse
