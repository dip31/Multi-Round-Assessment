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
    score: Optional[float] = None
    duration: str


class OptimizationArea(BaseModel):
    title: str
    description: str
    severity: str  # "warning" or "info"


class AnalyticsResponse(BaseModel):
    overall_score: float
    accuracy: float
    percentile: Optional[int] = None
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
            percentile=None,
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
    
    TECHNICAL_TOPIC_NAMES = {
        "Operating Systems",
        "Computer Networks",
        "Object-Oriented Programming",
        "Database Management Systems",
        "Data Structures",
    }

    # 1. Aptitude & Practice Round metrics
    completed_apt_rounds = [
        r for r in rounds 
        if r.round_type in ("aptitude", "mcq", "technical", "combined") and r.status == "completed"
    ]
    if completed_apt_rounds:
        completed_rounds.append("aptitude")
        apt_round_ids = [r.id for r in completed_apt_rounds]
        attempts = db.query(AptitudeAttempt).filter(
            AptitudeAttempt.round_id.in_(apt_round_ids)
        ).all()
        
        apt_total = len(attempts)
        apt_correct = sum(1 for a in attempts if a.is_correct)
        total_questions += apt_total
        correct_answers += apt_correct
        
        for a in attempts:
            if a.response_time:
                total_response_time += a.response_time
                response_count += 1
        
        # Topic-level and Technical Subject-level breakdown
        topic_groups = {}
        for a in attempts:
            t_name = a.question.topic.name if a.question and a.question.topic else None
            if t_name:
                topic_groups.setdefault(t_name, []).append(a)

        for t_name, att_list in sorted(topic_groups.items()):
            t_total = len(att_list)
            t_correct = sum(1 for a in att_list if a.is_correct)
            t_acc = round((t_correct / t_total) * 100, 1) if t_total > 0 else 0.0
            skill_breakdown.append(SkillBreakdownItem(
                name=t_name,
                score=t_acc
            ))

        if not skill_breakdown:
            latest_apt = completed_apt_rounds[-1]
            apt_score = latest_apt.score if latest_apt.score is not None else 0.0
            skill_breakdown.append(SkillBreakdownItem(
                name="Quantitative Aptitude",
                score=round(apt_score * 100, 1)
            ))
        
        for r in completed_apt_rounds:
            dur = f"{max(1, int((r.completed_at - r.started_at).total_seconds() // 60))}m" if r.completed_at and r.started_at else "30m"
            r_attempts = [a for a in attempts if a.round_id == r.id]
            r_topics = {a.question.topic.name for a in r_attempts if a.question and a.question.topic}
            
            # Determine authoritative round label
            if r.round_type == "technical":
                round_label = "Technical Round"
            elif r.round_type == "combined":
                round_label = "Combined Round"
            elif r.round_type == "mcq":
                round_label = "MCQ Round"
            else:
                has_tech = any(t in TECHNICAL_TOPIC_NAMES for t in r_topics)
                has_mcq = any(t not in TECHNICAL_TOPIC_NAMES for t in r_topics)
                if has_tech and has_mcq:
                    round_label = "Combined Round"
                elif has_tech:
                    round_label = "Technical Round"
                else:
                    round_label = "MCQ Round (Aptitude)"

            session_history.append(SessionHistoryItem(
                id=f"PRAC-{r.id}",
                type=round_label,
                date=r.completed_at.strftime("%b %d, %Y") if r.completed_at else "Recent",
                score=round((r.score or 0.0) * 100, 1),
                duration=dur
            ))
    
    # 2. Coding metrics
    completed_cod_rounds = [r for r in rounds if r.round_type == "coding" and r.status == "completed"]
    if completed_cod_rounds:
        completed_rounds.append("coding")
        cod_round_ids = [r.id for r in completed_cod_rounds]
        
        from app.models.coding import CodingSubmission
        cod_submissions = db.query(CodingSubmission).filter(
            CodingSubmission.round_id.in_(cod_round_ids)
        ).all()
        
        cod_total = len(cod_submissions)
        cod_correct = sum(1 for s in cod_submissions if (s.score or 0) >= 0.7)
        total_questions += cod_total
        correct_answers += cod_correct
        
        latest_cod = completed_cod_rounds[-1]
        coding_score = latest_cod.score if latest_cod.score is not None else 0.0
        skill_breakdown.append(SkillBreakdownItem(
            name="Coding Proficiency",
            score=round(coding_score * 100, 1)
        ))
        
        for r in completed_cod_rounds:
            dur = f"{max(1, int((r.completed_at - r.started_at).total_seconds() // 60))}m" if r.completed_at and r.started_at else "30m"
            session_history.append(SessionHistoryItem(
                id=f"COD-{r.id}",
                type="Coding Challenge",
                date=r.completed_at.strftime("%b %d, %Y") if r.completed_at else "Recent",
                score=round((r.score or 0.0) * 100, 1),
                duration=dur
            ))
    
    # 3. Interview metrics
    # Select only the fields used below. In particular, analytics does not
    # depend on the optional round_id added for round-specific interview results.
    interview_sessions = db.query(
        InterviewSession.id,
        InterviewSession.session_id,
        InterviewSession.phase,
        InterviewSession.status,
        InterviewSession.rl_state,
        InterviewSession.created_at,
        InterviewSession.personalization_metadata,
    ).filter(
        InterviewSession.session_id.in_(session_ids)
    ).all()
    retell_hosted_session_ids = {
        s.session_id
        for s in interview_sessions
        if (s.personalization_metadata or {}).get("voice_mode") == "retell_hosted"
    }
    completed_int_rounds = [
        r for r in rounds 
        if r.round_type in ("interview", "technical_interview", "hr_interview", "communication_interview") 
        and r.status == "completed"
    ]
    completed_int_sessions = [s for s in interview_sessions if s.phase == "COMPLETE" or s.status == "COMPLETED"]
    
    if completed_int_rounds or completed_int_sessions:
        if "interview" not in completed_rounds:
            completed_rounds.append("interview")
        
        interview_session_ids = [s.id for s in interview_sessions]
        turns = db.query(InterviewTurn).filter(
            InterviewTurn.interview_id.in_(interview_session_ids),
            InterviewTurn.is_followup == False
        ).all()
        
        int_total = len(turns)
        int_correct = sum(1 for t in turns if t.final_score and t.final_score >= 0.5)
        total_questions += int_total
        correct_answers += int_correct
        int_score = None
        
        for t in turns:
            if t.response_time_sec:
                total_response_time += t.response_time_sec
                response_count += 1
        
        scored_int_rounds = [
            r for r in completed_int_rounds
            if r.session_id not in retell_hosted_session_ids
        ]
        if turns or scored_int_rounds:
            latest_int = scored_int_rounds[-1] if scored_int_rounds else None
            int_score = latest_int.score if latest_int and latest_int.score is not None else 0.0
            skill_breakdown.append(SkillBreakdownItem(
                name="Interview Simulation",
                score=round(int_score * 100, 1)
            ))
        
        def resolve_interview_label(sess, rnd=None):
            if rnd and rnd.round_type == "hr_interview":
                return "HR Interview"
            if rnd and rnd.round_type == "communication_interview":
                return "Communication Interview"
            if rnd and rnd.round_type == "technical_interview":
                return "Technical Interview"
            if sess and sess.rl_state:
                itype = sess.rl_state.get("interview_type", "").lower()
                if "hr" in itype:
                    return "HR Interview"
                if "communication" in itype:
                    return "Communication Interview"
                if "technical" in itype:
                    return "Technical Interview"
            if sess and sess.phase:
                if sess.phase.upper() == "COMMUNICATION":
                    return "Communication Interview"
                if sess.phase.upper() == "HR":
                    return "HR Interview"
            return "Technical Interview"

        for r in completed_int_rounds:
            dur = f"{max(1, int((r.completed_at - r.started_at).total_seconds() // 60))}m" if r.completed_at and r.started_at else "25m"
            matching_sess = next((s for s in interview_sessions if s.session_id == r.session_id), None)
            lbl = resolve_interview_label(matching_sess, r)
            session_history.append(SessionHistoryItem(
                id=f"INT-{r.id}",
                type=lbl,
                date=r.completed_at.strftime("%b %d, %Y") if r.completed_at else "Recent",
                score=(
                    None
                    if r.session_id in retell_hosted_session_ids
                    and not any(
                        s.session_id == r.session_id and s.id in {t.interview_id for t in turns}
                        for s in interview_sessions
                    )
                    else round((r.score or 0.0) * 100, 1)
                ),
                duration=dur
            ))
        if not completed_int_rounds and completed_int_sessions:
            for s in completed_int_sessions:
                lbl = resolve_interview_label(s, None)
                session_history.append(SessionHistoryItem(
                    id=f"INT-S{s.id}",
                    type=lbl,
                    date=s.created_at.strftime("%b %d, %Y") if s.created_at else "Recent",
                    score=(
                        None
                        if s.session_id in retell_hosted_session_ids or int_score is None
                        else round(int_score * 100, 1)
                    ),
                    duration="25m"
                ))
    
    # Calculate overall metrics
    scored_rounds = [r.score for r in rounds if r.status == "completed" and r.score is not None and r.score > 0]
    best_session = max(sessions, key=lambda s: s.total_score or 0) if sessions else None
    if best_session and (best_session.total_score or 0) > 0:
        overall_score = round((best_session.total_score or 0) * 100, 1)
    elif scored_rounds:
        overall_score = round((sum(scored_rounds) / len(scored_rounds)) * 100, 1)
    elif skill_breakdown:
        overall_score = round(sum(s.score for s in skill_breakdown) / len(skill_breakdown), 1)
    else:
        overall_score = 0.0
    
    accuracy = round((correct_answers / total_questions * 100), 1) if total_questions > 0 else 0.0
    avg_response_time = round(total_response_time / response_count, 1) if response_count > 0 else 0.0
    
    # Calculate percentile against student cohort with scores
    if total_questions == 0 and overall_score == 0:
        percentile = None
    else:
        all_scores = db.query(AssessmentSession.total_score).join(
            User, User.id == AssessmentSession.user_id
        ).filter(
            User.role == "student",
            AssessmentSession.total_score != None,
            AssessmentSession.total_score > 0
        ).all()
        
        all_scores = [float(s[0]) for s in all_scores if s[0] is not None]
        if len(all_scores) > 1 and overall_score > 0:
            scores_below = sum(1 for s in all_scores if (s * 100) < overall_score)
            percentile = max(1, min(99, round((scores_below / (len(all_scores) - 1)) * 100)))
        elif len(all_scores) == 1 and overall_score > 0:
            percentile = 100
        else:
            percentile = None
    
    # Generate transparent rule-based optimization insights
    optimization_areas = []
    for skill in skill_breakdown:
        if skill.score < 50:
            optimization_areas.append(OptimizationArea(
                title=f"Improve {skill.name}",
                description=f"Your {skill.name.lower()} score of {skill.score}% is below benchmark. Focus on targeted practice in this area.",
                severity="warning"
            ))
        elif skill.score < 70:
            optimization_areas.append(OptimizationArea(
                title=f"Practice {skill.name}",
                description=f"Your {skill.name.lower()} score shows room for improvement. Consider additional practice rounds.",
                severity="info"
            ))
    
    if avg_response_time > 60:
        optimization_areas.append(OptimizationArea(
            title="Response Time Pacing",
            description=f"Your average response time ({avg_response_time}s) is above benchmark (60s). Practice under timed conditions.",
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


@router.get("/student-analytics")
def get_detailed_student_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Real-data driven, backend-authoritative student analytics endpoint.
    Restricted to authenticated student's own data.
    """
    from app.models.coding import CodingSubmission
    from app.models.aptitude import AptitudeTopic

    user_id = current_user.id

    # 1. Fetch user sessions
    sessions = (
        db.query(AssessmentSession)
        .filter(AssessmentSession.user_id == user_id)
        .order_by(AssessmentSession.started_at.desc())
        .all()
    )
    session_ids = [s.id for s in sessions]

    # 2. Fetch rounds for these sessions
    rounds = (
        db.query(AssessmentRound)
        .filter(AssessmentRound.session_id.in_(session_ids))
        .order_by(AssessmentRound.started_at.asc())
        .all()
    ) if session_ids else []

    # 3. Fetch aptitude/mcq attempts
    round_ids = [r.id for r in rounds]
    attempts = (
        db.query(AptitudeAttempt)
        .filter(AptitudeAttempt.round_id.in_(round_ids))
        .all()
    ) if round_ids else []

    # 4. Fetch coding submissions
    cod_round_ids = [r.id for r in rounds if r.round_type == "coding"]
    cod_submissions = (
        db.query(CodingSubmission)
        .filter(CodingSubmission.round_id.in_(cod_round_ids))
        .all()
    ) if cod_round_ids else []

    # 5. Fetch interview sessions & turns
    interview_sessions = (
        db.query(InterviewSession)
        .filter(InterviewSession.session_id.in_(session_ids))
        .all()
    ) if session_ids else []
    int_sess_ids = [s.id for s in interview_sessions]
    interview_turns = (
        db.query(InterviewTurn)
        .filter(InterviewTurn.interview_id.in_(int_sess_ids))
        .all()
    ) if int_sess_ids else []

    # Technical subjects map
    SUBJECT_MAPPING = {
        "Operating Systems": ["Operating Systems", "OS"],
        "Computer Networks": ["Computer Networks", "CN"],
        "Object-Oriented Programming": ["Object-Oriented Programming", "OOPS"],
        "Database Management Systems": ["Database Management Systems", "DBMS"],
        "Data Structures": ["Data Structures", "DSA", "Data Structures & Algorithms"],
    }
    MCQ_TOPIC_NAMES = {
        "Quantitative Aptitude", "Logical Reasoning", "Verbal Ability", "Data Interpretation"
    }

    # Helper to map topic to standard subject
    def resolve_subject_from_topic(t_name: str | None) -> str | None:
        if not t_name:
            return None
        for std_subj, aliases in SUBJECT_MAPPING.items():
            if t_name in aliases:
                return std_subj
        return None

    # Group attempts by subject
    subject_stats = {
        subj: {"attempted": 0, "correct": 0, "scores": []}
        for subj in SUBJECT_MAPPING
    }
    topic_stats = {}
    difficulty_stats = {
        "easy": {"attempted": 0, "correct": 0},
        "medium": {"attempted": 0, "correct": 0},
        "hard": {"attempted": 0, "correct": 0},
    }

    mcq_attempted = 0
    mcq_correct = 0
    tech_attempted = 0
    tech_correct = 0

    for att in attempts:
        q = att.question
        t_name = q.topic.name if q and q.topic else "General"
        std_subj = resolve_subject_from_topic(t_name)

        diff = (att.difficulty or (q.difficulty if q else "medium")).lower()
        if diff in difficulty_stats:
            difficulty_stats[diff]["attempted"] += 1
            if att.is_correct:
                difficulty_stats[diff]["correct"] += 1

        is_tech = std_subj is not None
        if is_tech:
            tech_attempted += 1
            if att.is_correct:
                tech_correct += 1
            subject_stats[std_subj]["attempted"] += 1
            if att.is_correct:
                subject_stats[std_subj]["correct"] += 1
        elif t_name in MCQ_TOPIC_NAMES:
            mcq_attempted += 1
            if att.is_correct:
                mcq_correct += 1

        # Topic aggregation
        topic_key = t_name
        if topic_key not in topic_stats:
            topic_stats[topic_key] = {
                "topic": topic_key,
                "subject": std_subj or "Aptitude",
                "attempted": 0,
                "correct": 0,
            }
        topic_stats[topic_key]["attempted"] += 1
        if att.is_correct:
            topic_stats[topic_key]["correct"] += 1

    # Format subjects array
    formatted_subjects = []
    for subj, data in subject_stats.items():
        att_cnt = data["attempted"]
        cor_cnt = data["correct"]
        acc = round((cor_cnt / att_cnt) * 100, 1) if att_cnt > 0 else None
        classification = "Not Attempted"
        if acc is not None:
            if acc >= 75.0:
                classification = "Strong"
            elif acc >= 50.0:
                classification = "Moderate"
            else:
                classification = "Weak"

        formatted_subjects.append({
            "subject": subj,
            "attempted": att_cnt,
            "correct": cor_cnt,
            "accuracy": acc,
            "avg_score": acc,
            "classification": classification,
        })

    # Format topics array
    formatted_topics = []
    for top_data in sorted(topic_stats.values(), key=lambda x: -x["attempted"]):
        t_att = top_data["attempted"]
        t_cor = top_data["correct"]
        formatted_topics.append({
            "topic": top_data["topic"],
            "subject": top_data["subject"],
            "attempted": t_att,
            "correct": t_cor,
            "accuracy": round((t_cor / t_att) * 100, 1) if t_att > 0 else 0.0,
        })

    # Format difficulty array
    formatted_difficulty = [
        {
            "level": lvl.capitalize(),
            "attempted": data["attempted"],
            "correct": data["correct"],
            "accuracy": round((data["correct"] / data["attempted"]) * 100, 1) if data["attempted"] > 0 else None,
        }
        for lvl, data in difficulty_stats.items()
    ]

    # Round-wise performance
    round_type_counts = {}
    for r in rounds:
        if r.status != "completed":
            continue
        rtype = r.round_type
        round_type_counts.setdefault(rtype, []).append(r)

    # Combined round specific split
    combined_rounds = round_type_counts.get("combined", [])
    comb_mcq_att = 0
    comb_mcq_cor = 0
    comb_tech_att = 0
    comb_tech_cor = 0
    if combined_rounds:
        comb_round_ids = [r.id for r in combined_rounds]
        comb_attempts = [a for a in attempts if a.round_id in comb_round_ids]
        for ca in comb_attempts:
            q = ca.question
            t_name = q.topic.name if q and q.topic else ""
            if resolve_subject_from_topic(t_name):
                comb_tech_att += 1
                if ca.is_correct:
                    comb_tech_cor += 1
            else:
                comb_mcq_att += 1
                if ca.is_correct:
                    comb_mcq_cor += 1

    formatted_rounds = []
    round_label_map = {
        "mcq": "MCQ Round",
        "aptitude": "MCQ Round",
        "technical": "Technical Round",
        "combined": "Combined Round",
        "coding": "Coding Challenge",
        "interview": "Interview Round",
        "technical_interview": "Technical Interview",
        "hr_interview": "HR Interview",
        "communication_interview": "Communication Interview",
    }

    for r_type, r_list in round_type_counts.items():
        r_scores = [float(r.score) * 100 for r in r_list if r.score is not None]
        avg_s = round(sum(r_scores) / len(r_scores), 1) if r_scores else None
        item = {
            "type": r_type,
            "name": round_label_map.get(r_type, r_type.replace("_", " ").title()),
            "attempts": len(r_list),
            "avg_score": avg_s,
        }
        if r_type == "combined" and (comb_mcq_att + comb_tech_att) > 0:
            item["mcq_attempted"] = comb_mcq_att
            item["mcq_accuracy"] = round((comb_mcq_cor / comb_mcq_att) * 100, 1) if comb_mcq_att > 0 else None
            item["technical_attempted"] = comb_tech_att
            item["technical_accuracy"] = round((comb_tech_cor / comb_tech_att) * 100, 1) if comb_tech_att > 0 else None
        formatted_rounds.append(item)

    # Coding analytics
    cod_solved = sum(1 for s in cod_submissions if (s.score or 0) >= 0.7)
    cod_success_rate = round((cod_solved / len(cod_submissions)) * 100, 1) if cod_submissions else None
    coding_analytics = {
        "problems_attempted": len(cod_submissions),
        "problems_solved": cod_solved,
        "success_rate": cod_success_rate,
        "test_cases_passed_pct": round(
            sum(
                (float(s.score) * 100)
                for s in cod_submissions
                if s.score is not None
            ) / len(cod_submissions),
            1,
        ) if cod_submissions else None,
    }

    # Interview analytics
    int_rounds_completed = [r for r in rounds if "interview" in r.round_type and r.status == "completed"]
    tech_ints = [r for r in int_rounds_completed if r.round_type in ("technical_interview", "interview")]
    hr_ints = [r for r in int_rounds_completed if r.round_type == "hr_interview"]
    comm_ints = [r for r in int_rounds_completed if r.round_type == "communication_interview"]

    def avg_score(r_list):
        scores = [float(r.score) * 100 for r in r_list if r.score is not None]
        return round(sum(scores) / len(scores), 1) if scores else None

    interview_analytics = {
        "technical": {
            "attempts": len(tech_ints),
            "score": avg_score(tech_ints),
        },
        "hr": {
            "attempts": len(hr_ints),
            "score": avg_score(hr_ints),
        },
        "communication": {
            "attempts": len(comm_ints),
            "score": avg_score(comm_ints),
        },
    }

    # Overview readiness calculations
    technical_readiness = round((tech_correct / tech_attempted) * 100, 1) if tech_attempted > 0 else None
    mcq_readiness = round((mcq_correct / mcq_attempted) * 100, 1) if mcq_attempted > 0 else None
    coding_readiness = avg_score([r for r in rounds if r.round_type == "coding" and r.status == "completed"])
    interview_readiness = avg_score(int_rounds_completed)
    comm_readiness = avg_score(comm_ints)

    # Weighted Overall Readiness
    weights = {
        "technical": (technical_readiness, 0.30),
        "mcq": (mcq_readiness, 0.25),
        "coding": (coding_readiness, 0.25),
        "interview": (interview_readiness, 0.20),
    }
    available_weights = [w for k, (val, w) in weights.items() if val is not None]
    if available_weights:
        total_w = sum(available_weights)
        overall_readiness = round(
            sum(val * w for val, w in [pair for pair in weights.values() if pair[0] is not None]) / total_w,
            1,
        )
    else:
        overall_readiness = None

    # Strengths and Focus Areas (data-driven with >= 2 attempts)
    strengths = []
    focus_areas = []
    for subj_item in formatted_subjects:
        if subj_item["attempted"] >= 2 and subj_item["accuracy"] is not None:
            if subj_item["accuracy"] >= 75.0:
                strengths.append({
                    "name": subj_item["subject"],
                    "score": subj_item["accuracy"],
                    "type": "Technical Subject",
                })
            elif subj_item["accuracy"] < 65.0:
                focus_areas.append({
                    "name": subj_item["subject"],
                    "score": subj_item["accuracy"],
                    "type": "Technical Subject",
                })

    if mcq_readiness is not None and mcq_attempted >= 5:
        if mcq_readiness >= 75.0:
            strengths.append({"name": "MCQ Aptitude", "score": mcq_readiness, "type": "Aptitude"})
        elif mcq_readiness < 65.0:
            focus_areas.append({"name": "MCQ Aptitude", "score": mcq_readiness, "type": "Aptitude"})

    if coding_readiness is not None:
        if coding_readiness >= 75.0:
            strengths.append({"name": "Coding Challenge", "score": coding_readiness, "type": "Coding"})
        elif coding_readiness < 65.0:
            focus_areas.append({"name": "Coding Challenge", "score": coding_readiness, "type": "Coding"})

    # Deterministic Next Practice Recommendation
    recommendation = None
    if focus_areas:
        worst_focus = min(focus_areas, key=lambda x: x["score"])
        recommendation = {
            "subject": worst_focus["name"],
            "difficulty": "Medium",
            "questions": 10,
            "reason": f"Your current score in {worst_focus['name']} ({worst_focus['score']}%) is below target. Practicing medium questions here will yield the largest readiness improvement.",
        }
    elif technical_readiness is not None and technical_readiness < 80.0:
        non_attempted = [s["subject"] for s in formatted_subjects if s["attempted"] == 0]
        rec_subj = non_attempted[0] if non_attempted else "Operating Systems"
        recommendation = {
            "subject": rec_subj,
            "difficulty": "Medium",
            "questions": 10,
            "reason": f"Broaden your CS fundamentals by practicing core {rec_subj} questions.",
        }
    elif difficulty_stats["easy"]["attempted"] >= 10 and (difficulty_stats["medium"]["attempted"] == 0 or (difficulty_stats["medium"]["correct"] / max(1, difficulty_stats["medium"]["attempted"])) < 0.7):
        recommendation = {
            "subject": "All Technical",
            "difficulty": "Medium",
            "questions": 10,
            "reason": "You have a solid base in Easy questions. Advance to Medium difficulty questions to raise your benchmark.",
        }
    else:
        recommendation = {
            "subject": "Combined Round",
            "difficulty": "Medium",
            "questions": 10,
            "reason": "Build multi-domain endurance with a 50/50 Aptitude and Technical Combined Practice session.",
        }

    # Chronological Trend (only completed rounds with scores)
    completed_rounds = [r for r in rounds if r.status == "completed" and r.score is not None]
    trend = [
        {
            "id": r.id,
            "session_id": r.session_id,
            "date": r.completed_at.strftime("%b %d") if r.completed_at else "Recent",
            "round_type": r.round_type,
            "round_name": round_label_map.get(r.round_type, r.round_type.title()),
            "score": round(float(r.score) * 100, 1),
        }
        for r in completed_rounds
    ]

    # Consistency metrics
    all_scores = [t["score"] for t in trend]
    consistency = {
        "best_score": max(all_scores) if all_scores else None,
        "avg_score": round(sum(all_scores) / len(all_scores), 1) if all_scores else None,
        "lowest_score": min(all_scores) if all_scores else None,
        "latest_score": all_scores[-1] if all_scores else None,
        "total_attempts": len(all_scores),
    }

    # Summary
    latest_completed = completed_rounds[-1].completed_at if completed_rounds else None
    summary = {
        "practice_sessions": len(completed_rounds),
        "questions_attempted": len(attempts) + len(cod_submissions) + len(interview_turns),
        "completed_sessions": len([s for s in sessions if s.status == "completed"]),
        "recent_activity": latest_completed.strftime("%b %d, %Y") if latest_completed else "No activity yet",
    }

    return {
        "overview": {
            "overall_readiness": overall_readiness,
            "technical": technical_readiness,
            "mcq": mcq_readiness,
            "coding": coding_readiness,
            "interview": interview_readiness,
            "communication": comm_readiness,
        },
        "summary": summary,
        "trend": trend,
        "subjects": formatted_subjects,
        "topics": formatted_topics,
        "rounds": formatted_rounds,
        "difficulty": formatted_difficulty,
        "coding": coding_analytics,
        "interviews": interview_analytics,
        "strengths": strengths,
        "focus_areas": focus_areas,
        "recommendation": recommendation,
        "consistency": consistency,
    }
