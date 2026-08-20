"""
Candidate-facing report endpoints for analytics.

GET /report/analytics - Get candidate's own analytics data
"""

from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from app.database.db import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.assessment import AssessmentSession, AssessmentRound
from app.models.interview import InterviewSession, InterviewTurn
from app.models.aptitude import AptitudeAttempt, AptitudeQuestion


# ── Response Schemas ───────────────────────────────────────────────────

class SkillBreakdownItem(BaseModel):
    name: str
    score: float
    max_score: float = 100


class SessionHistoryItem(BaseModel):
    id: str
    type: str
    date: str
    score: float
    duration: str


class OptimizationArea(BaseModel):
    title: str
    description: str
    severity: str  # "warning" or "info"


class AnalyticsResponse(BaseModel):
    overall_score: float
    accuracy: float
    percentile: int
    total_questions: int
    completed_rounds: List[str]
    skill_breakdown: List[SkillBreakdownItem]
    session_history: List[SessionHistoryItem]
    optimization_areas: List[OptimizationArea]
    avg_response_time: float
    benchmark_response_time: float = 60.0


router = APIRouter(prefix="/report", tags=["Candidate Reporting"])


@router.get("/analytics", response_model=AnalyticsResponse)
def get_candidate_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AnalyticsResponse:
    """Get comprehensive analytics for the current candidate."""
    
    user_id = current_user.id
    
    # Get all sessions for this user
    sessions = db.query(AssessmentSession).filter(
        AssessmentSession.user_id == user_id
    ).all()
    
    if not sessions:
        return AnalyticsResponse(
            overall_score=0,
            accuracy=0,
            percentile=0,
            total_questions=0,
            completed_rounds=[],
            skill_breakdown=[],
            session_history=[],
            optimization_areas=[],
            avg_response_time=0
        )
    
    # Get all rounds for all sessions
    session_ids = [s.id for s in sessions]
    rounds = db.query(AssessmentRound).filter(
        AssessmentRound.session_id.in_(session_ids)
    ).all()
    
    completed_rounds = []
    skill_breakdown = []
    session_history = []
    total_questions = 0
    correct_answers = 0
    total_response_time = 0
    response_count = 0
    
    # Calculate aptitude metrics
    aptitude_round = next((r for r in rounds if r.round_type == "aptitude" and r.status == "completed"), None)
    if aptitude_round:
        completed_rounds.append("aptitude")
        
        # Get aptitude attempts
        attempts = db.query(AptitudeAttempt).filter(
            AptitudeAttempt.round_id == aptitude_round.id
        ).all()
        
        apt_total = len(attempts)
        apt_correct = sum(1 for a in attempts if a.is_correct)
        total_questions += apt_total
        correct_answers += apt_correct
        
        for a in attempts:
            if a.response_time:
                total_response_time += a.response_time
                response_count += 1
        
        apt_score = aptitude_round.score if aptitude_round.score else 0
        skill_breakdown.append(SkillBreakdownItem(
            name="Quantitative Aptitude",
            score=round(apt_score * 100, 1)
        ))
        
        session_history.append(SessionHistoryItem(
            id=f"APT-{aptitude_round.id}",
            type="Aptitude Assessment",
            date=aptitude_round.completed_at.strftime("%b %d, %Y") if aptitude_round.completed_at else "Unknown",
            score=round(apt_score * 100, 1),
            duration=f"{int((aptitude_round.completed_at - aptitude_round.started_at).total_seconds() // 60)}m" if aptitude_round.completed_at and aptitude_round.started_at else "N/A"
        ))
    
    # Calculate interview metrics
    interview_round = next((r for r in rounds if r.round_type == "interview" and r.status == "completed"), None)
    if interview_round:
        completed_rounds.append("interview")
        
        # Get interview sessions and turns
        interview_sessions = db.query(InterviewSession).filter(
            InterviewSession.user_id == user_id
        ).all()
        
        interview_session_ids = [s.id for s in interview_sessions]
        turns = db.query(InterviewTurn).filter(
            InterviewTurn.interview_id.in_(interview_session_ids),
            InterviewTurn.is_followup == False
        ).all()
        
        int_total = len(turns)
        int_correct = sum(1 for t in turns if t.final_score and t.final_score >= 0.5)
        total_questions += int_total
        correct_answers += int_correct
        
        for t in turns:
            if t.response_time_sec:
                total_response_time += t.response_time_sec
                response_count += 1
        
        int_score = interview_round.score if interview_round.score else 0
        skill_breakdown.append(SkillBreakdownItem(
            name="Interview Simulation",
            score=round(int_score * 100, 1)
        ))
        
        session_history.append(SessionHistoryItem(
            id=f"INT-{interview_round.id}",
            type="AI Mock Interview",
            date=interview_round.completed_at.strftime("%b %d, %Y") if interview_round.completed_at else "Unknown",
            score=round(int_score * 100, 1),
            duration=f"{int((interview_round.completed_at - interview_round.started_at).total_seconds() // 60)}m" if interview_round.completed_at and interview_round.started_at else "N/A"
        ))
    
    # Coding round (placeholder for now)
    coding_round = next((r for r in rounds if r.round_type == "coding" and r.status == "completed"), None)
    if coding_round:
        completed_rounds.append("coding")
        coding_score = coding_round.score if coding_round.score else 0
        skill_breakdown.append(SkillBreakdownItem(
            name="Coding Proficiency",
            score=round(coding_score * 100, 1)
        ))
    
    # Calculate overall metrics
    best_session = max(sessions, key=lambda s: s.total_score or 0)
    overall_score = round((best_session.total_score or 0) * 100, 1)
    
    accuracy = round((correct_answers / total_questions * 100), 1) if total_questions > 0 else 0
    avg_response_time = round(total_response_time / response_count, 1) if response_count > 0 else 0
    
    # Calculate percentile (compare against all students)
    all_scores = db.query(AssessmentSession.total_score).join(
        User, User.id == AssessmentSession.user_id
    ).filter(
        User.role == "student",
        AssessmentSession.total_score != None
    ).all()
    
    all_scores = [s[0] for s in all_scores if s[0] is not None]
    if len(all_scores) > 1:
        scores_below = sum(1 for s in all_scores if s < (best_session.total_score or 0))
        percentile = round((scores_below / (len(all_scores) - 1)) * 100)
    elif len(all_scores) == 1:
        percentile = 100
    else:
        percentile = 0
    
    # Generate optimization areas based on performance
    optimization_areas = []
    
    for skill in skill_breakdown:
        if skill.score < 50:
            optimization_areas.append(OptimizationArea(
                title=f"Improve {skill.name}",
                description=f"Your {skill.name.lower()} score of {skill.score}% is below average. Focus on practice exercises in this area.",
                severity="warning"
            ))
        elif skill.score < 70:
            optimization_areas.append(OptimizationArea(
                title=f"Practice {skill.name}",
                description=f"Your {skill.name.lower()} score shows room for improvement. Consider targeted practice.",
                severity="info"
            ))
    
    if avg_response_time > 60:
        optimization_areas.append(OptimizationArea(
            title="Response Time",
            description="Your average response time is above benchmark. Practice under timed conditions.",
            severity="info"
        ))
    
    return AnalyticsResponse(
        overall_score=overall_score,
        accuracy=accuracy,
        percentile=percentile,
        total_questions=total_questions,
        completed_rounds=completed_rounds,
        skill_breakdown=skill_breakdown,
        session_history=session_history,
        optimization_areas=optimization_areas,
        avg_response_time=avg_response_time,
        benchmark_response_time=60.0
    )
