from pydantic import BaseModel
from typing import Dict


class NextQuestionResponse(BaseModel):
    question_id: int
    question_text: str
    options: Dict[str, str]
    difficulty: str


class SubmitAnswerRequest(BaseModel):
    question_id: int
    selected_option: str
    response_time: float


class SubmitAnswerResponse(BaseModel):
    correct: bool
    correct_option: str


class RoundResultResponse(BaseModel):
    total_questions: int
    correct_answers: int
    accuracy: float