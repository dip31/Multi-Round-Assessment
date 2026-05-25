from typing import List
from difflib import SequenceMatcher
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, case

from app.database.db import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.assessment import AssessmentSession, AssessmentRound
from app.models.interview import InterviewSession, InterviewTurn, ApprovedQuestionPool
from app.models.aptitude import AptitudeAttempt
from app.modules.report.schemas.report_schema import (
    CohortStatsResponse, 
    SkillGapsResponse, 
    AllCandidatesResponse,
    CompletionRates,
    CandidateListItem,
    SkillGapItem
)

router = APIRouter(prefix="/report/admin", tags=["Admin Reporting"])

def check_admin(current_user: User):
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires admin privileges"
        )

@router.get("/cohort-stats", response_model=CohortStatsResponse)
def get_cohort_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CohortStatsResponse:
    """Get aggregated performance metrics across all candidates."""
    check_admin(current_user)

    # 1. Total Candidates
    total_candidates = db.query(User).filter(User.role == "student").count()
    if total_candidates == 0:
        return CohortStatsResponse(
            total_candidates=0,
            avg_aptitude_score=0,
            avg_coding_score=0,
            avg_interview_score=0,
            avg_overall_score=0,
            completion_rates=CompletionRates(aptitude=0, coding=0, interview=0, all_three=0),
            avg_followup_rate=0,
            avg_response_time=0
        )

    # 2. Average Scores by Module
    avg_aptitude = db.query(func.avg(AssessmentRound.score)).filter(AssessmentRound.round_type == "aptitude", AssessmentRound.status == "completed").scalar() or 0
    avg_coding = db.query(func.avg(AssessmentRound.score)).filter(AssessmentRound.round_type == "coding", AssessmentRound.status == "completed").scalar() or 0
    avg_interview = db.query(func.avg(AssessmentRound.score)).filter(AssessmentRound.round_type == "interview", AssessmentRound.status == "completed").scalar() or 0
    avg_overall = db.query(func.avg(AssessmentSession.total_score)).filter(AssessmentSession.status == "completed").scalar() or 0

    # 3. Completion Rates
    # aptitude_completed = db.query(AssessmentRound).filter(AssessmentRound.round_type == "aptitude", AssessmentRound.status == "completed").distinct(AssessmentRound.session_id).count()
    # (Simplified for performance)
    aptitude_count = db.query(func.count(func.distinct(AssessmentRound.session_id))).filter(AssessmentRound.round_type == "aptitude", AssessmentRound.status == "completed").scalar() or 0
    coding_count = db.query(func.count(func.distinct(AssessmentRound.session_id))).filter(AssessmentRound.round_type == "coding", AssessmentRound.status == "completed").scalar() or 0
    interview_count = db.query(func.count(func.distinct(AssessmentRound.session_id))).filter(AssessmentRound.round_type == "interview", AssessmentRound.status == "completed").scalar() or 0
    
    # All 3 completion: count sessions that have 3 completed rounds
    all_three_count = db.query(AssessmentRound.session_id).filter(AssessmentRound.status == "completed").group_by(AssessmentRound.session_id).having(func.count(AssessmentRound.id) >= 3).count()

    completion_rates = CompletionRates(
        aptitude=aptitude_count / total_candidates,
        coding=coding_count / total_candidates,
        interview=interview_count / total_candidates,
        all_three=all_three_count / total_candidates
    )

    # 4. Average Followup and Response Time (Interview Round focus)
    avg_followup_rate = 0
    # followup_rate = total_followups / total_main_turns
    total_main = db.query(InterviewTurn).filter(InterviewTurn.is_followup == False).count()
    total_followups = db.query(InterviewTurn).filter(InterviewTurn.is_followup == True).count()
    if total_main > 0:
        avg_followup_rate = (total_followups / total_main) * 100

    avg_resp_interview = db.query(func.avg(InterviewTurn.response_time_sec)).filter(InterviewTurn.candidate_response != None).scalar() or 0
    avg_resp_aptitude = db.query(func.avg(AptitudeAttempt.response_time)).filter(AptitudeAttempt.selected_option != None).scalar() or 0
    
    # Combined average response time
    if avg_resp_interview > 0 and avg_resp_aptitude > 0:
        avg_response_time = (avg_resp_interview + avg_resp_aptitude) / 2
    else:
        avg_response_time = avg_resp_interview or avg_resp_aptitude

    return CohortStatsResponse(
        total_candidates=total_candidates,
        avg_aptitude_score=round(avg_aptitude, 4),
        avg_coding_score=round(avg_coding, 4),
        avg_interview_score=round(avg_interview, 4),
        avg_overall_score=round(avg_overall, 4),
        completion_rates=completion_rates,
        avg_followup_rate=round(avg_followup_rate, 2),
        avg_response_time=round(avg_response_time, 2)
    )

@router.get("/skill-gaps", response_model=SkillGapsResponse)
def get_skill_gaps(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SkillGapsResponse:
    """Identify topics where candidates are struggling based on interview results.
    
    Uses fuzzy matching to handle rephrased questions from Groq.
    """
    check_admin(current_user)

    # Step 1: Build topic map from ALL question pools
    # key: original question text (lowercase stripped)
    # value: topic string
    topic_map = {}
    
    pools = db.query(ApprovedQuestionPool).all()
    for pool in pools:
        if not pool.question_pool:
            continue
        for q in pool.question_pool:
            if isinstance(q, dict):
                original = q.get("question", "").strip().lower()
                topic = q.get("topic", "General")
                if original:
                    topic_map[original] = topic

    def find_topic(question_text: str) -> str:
        """
        Find topic for a question using:
        1. Exact match (after lowercase + strip)
        2. Fuzzy match if exact fails (threshold 0.6)
        3. Default to "General" if no match
        """
        if not question_text:
            return "General"
        
        cleaned = question_text.strip().lower()
        
        # Exact match first
        if cleaned in topic_map:
            return topic_map[cleaned]
        
        # Fuzzy match
        best_score = 0.0
        best_topic = "General"
        for original, topic in topic_map.items():
            score = SequenceMatcher(None, cleaned, original).ratio()
            if score > best_score:
                best_score = score
                best_topic = topic
        
        # Only use fuzzy match if similarity >= 0.6
        if best_score >= 0.6:
            return best_topic
        return "General"

    # Step 2: Fetch all completed interview turns
    # Only main turns (is_followup=False) for clean data
    turns = db.query(InterviewTurn).filter(
        InterviewTurn.is_followup == False,
        InterviewTurn.final_score != None
    ).all()

    if not turns:
        return SkillGapsResponse(topics=[], total_turns_analyzed=0)

    # Step 3: Group turns by topic
    topic_data = defaultdict(lambda: {
        "scores": [],
        "candidate_ids": set()
    })

    for turn in turns:
        topic = find_topic(turn.question_text)
        score = turn.final_score or 0.0
        topic_data[topic]["scores"].append(score)
        
        # Get candidate id via interview session
        session = db.query(InterviewSession).filter(
            InterviewSession.id == turn.interview_id
        ).first()
        if session:
            topic_data[topic]["candidate_ids"].add(session.session_id)

    # Step 4: Compute metrics per topic
    results = []
    for topic, data in topic_data.items():
        scores = data["scores"]
        avg_score = sum(scores) / len(scores)
        struggle_count = sum(1 for s in scores if s < 0.5)
        struggle_rate = struggle_count / len(scores)
        
        results.append(SkillGapItem(
            topic=topic,
            avg_score=round(avg_score, 4),
            candidate_count=len(data["candidate_ids"]),
            question_count=len(scores),
            struggle_rate=round(struggle_rate, 4)
        ))

    # Sort by struggle_rate descending (worst first)
    results.sort(key=lambda x: x.struggle_rate, reverse=True)

    return SkillGapsResponse(topics=results, total_turns_analyzed=len(turns))

@router.get("/all-candidates", response_model=AllCandidatesResponse)
def get_all_candidates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AllCandidatesResponse:
    """List all student candidates with their overall scores and ranks.
    
    Percentile = % of candidates scoring BELOW this candidate.
    Examples with 10 candidates:
        Rank 1 (lowest score)  → percentile 0
        Rank 10 (highest score) → percentile 100
        Rank 5 of 10           → percentile ~44
    """
    check_admin(current_user)

    # Subquery to get the latest session score for each student
    candidates_raw = db.query(
        User.id,
        User.name,
        User.email,
        func.max(AssessmentSession.total_score).label("top_score"),
        func.max(AssessmentSession.status).label("status")
    ).outerjoin(
        AssessmentSession, User.id == AssessmentSession.user_id
    ).filter(User.role == "student").group_by(User.id).all()

    total_count = len(candidates_raw)
    
    if total_count == 0:
        return AllCandidatesResponse(candidates=[])

    # Build list with scores
    candidates_with_scores = []
    for user_id, name, email, score, status in candidates_raw:
        candidates_with_scores.append({
            "user_id": user_id,
            "name": name or "Unknown",
            "email": email,
            "overall_score": float(score) if score else 0.0,
            "status": status or "not_started"
        })

    # Compute percentiles using correct formula
    def compute_percentiles(candidates: list) -> list:
        """
        Percentile = % of OTHER candidates scoring below.
        """
        n = len(candidates)
        if n == 1:
            candidates[0]["percentile"] = 100
            return candidates
        
        # Sort by score ascending for percentile calc
        sorted_by_score = sorted(candidates, key=lambda x: x["overall_score"])
        
        for i, candidate in enumerate(sorted_by_score):
            candidate["percentile"] = round((i / (n - 1)) * 100) if n > 1 else 100
        
        return candidates

    candidates_with_scores = compute_percentiles(candidates_with_scores)

    # Sort by score descending and assign ranks
    sorted_candidates = sorted(
        candidates_with_scores,
        key=lambda x: x["overall_score"],
        reverse=True
    )
    
    results = []
    for rank, c in enumerate(sorted_candidates, start=1):
        results.append(CandidateListItem(
            user_id=c["user_id"],
            name=c["name"],
            email=c["email"],
            overall_score=round(c["overall_score"], 4),
            percentile=c["percentile"],
            rank=rank,
            status=c["status"]
        ))

    return AllCandidatesResponse(candidates=results)
