"""Schemas for the admin question review dashboard."""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


DifficultyValue = Literal["easy", "medium", "hard"]
QuestionStatusValue = Literal["approved", "rejected", "needs_review"]
InsightTypeValue = Literal["too_hard", "too_easy", "confusing", "balanced"]
FeedbackActionValue = Literal["approve", "reject", "review"]


class AdminQuestionListItem(BaseModel):
    id: int
    question_text: str
    difficulty: DifficultyValue
    attempts: int
    accuracy: float
    avg_time: float
    status: QuestionStatusValue
    needs_attention: bool


class AdminQuestionListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    questions: List[AdminQuestionListItem]


class RLDataResponse(BaseModel):
    in_active_pool: bool
    times_served: int
    last_served: Optional[datetime] = None
    avg_accuracy_when_served: float


class AdminQuestionDetailResponse(BaseModel):
    id: int
    question_text: str
    options: List[str]
    correct_option: str
    difficulty: DifficultyValue
    attempts: int
    accuracy: float
    avg_time: float
    insight: str
    insight_type: InsightTypeValue
    recommendation: Literal["approve", "review", "reject"]
    rl_data: RLDataResponse
    suggestion: Optional[str] = None


class AdminQuestionStatusUpdateRequest(BaseModel):
    status: Literal["approved", "rejected"]


class AdminQuestionFeedbackRequest(BaseModel):
    suggestion: str = Field(..., min_length=1)
    action: FeedbackActionValue


class AdminQuestionActionResponse(BaseModel):
    success: bool
    message: str
