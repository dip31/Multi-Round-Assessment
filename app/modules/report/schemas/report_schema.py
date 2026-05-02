from typing import List, Dict, Optional
from pydantic import BaseModel

class CompletionRates(BaseModel):
    aptitude: float
    coding: float
    interview: float
    all_three: float

class CohortStatsResponse(BaseModel):
    total_candidates: int
    avg_aptitude_score: float
    avg_coding_score: float
    avg_interview_score: float
    avg_overall_score: float
    completion_rates: CompletionRates
    avg_followup_rate: float
    avg_response_time: float

class SkillGapItem(BaseModel):
    topic: str
    avg_score: float
    candidate_count: int
    question_count: int = 0
    struggle_rate: float

class SkillGapsResponse(BaseModel):
    topics: List[SkillGapItem]
    total_turns_analyzed: int = 0

class CandidateListItem(BaseModel):
    user_id: int
    name: str
    email: str
    overall_score: float
    percentile: float
    rank: int
    status: str

class AllCandidatesResponse(BaseModel):
    candidates: List[CandidateListItem]
