"""
Pydantic schemas for aptitude round request / response payloads.
"""

from typing import Dict, Optional, List

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


class RoundResultResponse(BaseModel):
    """Summary statistics for a completed aptitude round."""
    total_questions: int
    correct_answers: int
    accuracy: float
    average_response_time: float
    longest_correct_streak: int
    difficulty_progression: List[str]
    rl_report: List[Dict]
