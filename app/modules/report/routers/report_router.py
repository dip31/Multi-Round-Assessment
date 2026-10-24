from typing import List, Optional
import logging
from difflib import SequenceMatcher
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, case, select

from app.database.db import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models import CompetencyEvidenceMapping
from app.models.assessment import AssessmentSession, AssessmentRound
from app.models.assessment_context import AssessmentContext
from app.models.mock_drive import MockDrive
from app.models.interview import InterviewSession, InterviewTurn, ApprovedQuestionPool
from app.models.coding import CodingSubmission
from app.models.aptitude import AptitudeAttempt, AptitudeQuestion, AptitudeTopic
from app.models.profile import StudentProfile
from app.modules.report.schemas.report_schema import (
    CohortStatsResponse,
    SkillGapsResponse,
    AllCandidatesResponse,
    CompletionRates,
    CandidateListItem,
    SkillGapItem
)

router = APIRouter(prefix="/report/admin", tags=["Admin & Staff Reporting"])
logger = logging.getLogger(__name__)

def check_admin(current_user: User):
    # These endpoints return institution-wide data. Faculty must use a
    # department-scoped reporting capability rather than this global surface.
    if current_user.role not in ("admin", "tpo"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Institution-wide reports require TPO or admin privileges"
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
            completed_sessions=0,
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
    completed_sessions = db.query(AssessmentSession).filter(
        AssessmentSession.status == "completed"
    ).count()
    avg_overall = db.query(func.avg(AssessmentSession.total_score)).filter(AssessmentSession.status == "completed").scalar() or 0

    # 3. Completion Rates
    # aptitude_completed = db.query(AssessmentRound).filter(AssessmentRound.round_type == "aptitude", AssessmentRound.status == "completed").distinct(AssessmentRound.session_id).count()
    # (Simplified for performance)
    completed_round_rows = (
        db.query(AssessmentSession.user_id, AssessmentSession.id, AssessmentRound.round_type)
        .join(AssessmentRound, AssessmentRound.session_id == AssessmentSession.id)
        .filter(AssessmentRound.status == "completed")
        .all()
    )
    canonical_round = {
        "aptitude": "aptitude", "mcq": "aptitude",
        "coding": "coding",
        "interview": "interview", "technical_interview": "interview",
        "hr_interview": "interview", "communication_interview": "interview",
    }
    students_by_type = {"aptitude": set(), "coding": set(), "interview": set()}
    types_by_session: dict[int, set[str]] = {}
    student_by_session: dict[int, int] = {}
    for user_id, session_id, round_type in completed_round_rows:
        round_key = canonical_round.get((round_type or "").lower())
        if round_key is None:
            continue
        students_by_type[round_key].add(user_id)
        types_by_session.setdefault(session_id, set()).add(round_key)
        student_by_session[session_id] = user_id
    all_three_students = {
        student_by_session[session_id]
        for session_id, types in types_by_session.items()
        if {"aptitude", "coding", "interview"}.issubset(types)
    }

    completion_rates = CompletionRates(
        aptitude=len(students_by_type["aptitude"]) / total_candidates,
        coding=len(students_by_type["coding"]) / total_candidates,
        interview=len(students_by_type["interview"]) / total_candidates,
        all_three=len(all_three_students) / total_candidates
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
        completed_sessions=completed_sessions,
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


# ── TPO Mock Drive Analytics ──────────────────────────────────────────
@router.get("/mock-drive-completion", response_model=dict)
def get_mock_drive_completion(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """TPO analytics: Mock Drive completion metrics and competency results.

    Completion is per-candidate (``AssessmentContext.status == "completed"``, set
    only after every enabled round finishes). A drive counts as completed when at
    least one candidate completed it. Draft drives are excluded. Round scores are
    reported exactly as persisted; no score is recomputed, rescaled, or invented.
    """
    check_admin(current_user)

    published_drives = (
        db.query(MockDrive)
        .filter(MockDrive.status.in_(("published", "active", "completed")))
        .order_by(MockDrive.id)
        .all()
    )
    total_drives = len(published_drives)

    drive_summaries = []
    completed_drives = 0
    scorable_session_ids = []

    for drive in published_drives:
        contexts = (
            db.query(AssessmentContext)
            .filter(
                AssessmentContext.mock_drive_id == drive.id,
                AssessmentContext.purpose == "mock_drive",
            )
            .all()
        )
        completed_candidates = sum(1 for ctx in contexts if ctx.status == "completed")
        if completed_candidates > 0:
            completed_drives += 1

        session_ids = []
        for ctx in contexts:
            sessions = (
                db.query(AssessmentSession)
                .filter(AssessmentSession.context_id == ctx.id)
                .all()
            )
            for sess in sessions:
                session_ids.append(sess.id)
                # Read-only safeguard: only score sessions whose context already
                # has a pinned snapshot, so scoring never backfills/persists state.
                if ctx.blueprint_snapshot:
                    scorable_session_ids.append(sess.id)

        if not session_ids:
            continue

        rounds = (
            db.query(AssessmentRound)
            .filter(
                AssessmentRound.session_id.in_(session_ids),
                AssessmentRound.status == "completed",
                AssessmentRound.score.isnot(None),
            )
            .all()
        )
        if not rounds:
            continue

        completed_rounds = [
            r for r in rounds
            if r.round_type in ("aptitude", "coding", "interview", "technical_interview", "hr_interview")
        ]
        scores = [r.score for r in rounds]
        avg_score = round(sum(scores) / len(scores), 2) if scores else None

        drive_summaries.append({
            "drive_id": drive.id,
            "company_name": drive.company_name,
            "target_role": drive.target_role,
            "total_rounds": len(completed_rounds),
            "total_candidates": len(contexts),
            "completed_candidates": completed_candidates,
            "aptitude_completed": len([r for r in completed_rounds if r.round_type == "aptitude"]),
            "coding_completed": len([r for r in completed_rounds if r.round_type == "coding"]),
            "interview_completed": len([
                r for r in completed_rounds
                if r.round_type in ("interview", "technical_interview", "hr_interview")
            ]),
            "avg_score": avg_score,
            "status": "completed" if completed_candidates > 0 else "in_progress",
        })

    # Competency-level results come from the authoritative scoring service (read-only).
    from app.services.competency_scoring_service import score_session_competencies

    by_competency: dict = {}
    for sid in scorable_session_ids:
        session = db.query(AssessmentSession).filter(AssessmentSession.id == sid).first()
        if session is None:
            continue
        scoring = score_session_competencies(db, session)
        for comp in scoring.get("competencies", []):
            entry = by_competency.setdefault(comp["competency_id"], {
                "scores": [],
                "evidence_counts": [],
                "statuses": [],
            })
            if comp["normalized_score"] is not None:
                entry["scores"].append(comp["normalized_score"])
            entry["evidence_counts"].append(comp["evidence_count"])
            entry["statuses"].append(comp["status"])

    competency_results = []
    for cid, entry in by_competency.items():
        scores = entry["scores"]
        evidence_counts = entry["evidence_counts"]
        statuses = entry["statuses"]
        competency_results.append({
            "competency_id": cid,
            "avg_score": round(sum(scores) / len(scores), 2) if scores else None,
            "evidence_count": sum(evidence_counts),
            "max_evidence": max(evidence_counts) if evidence_counts else 0,
            "status_distribution": {
                "assessed": sum(1 for s in statuses if s == "assessed"),
                "not_assessed": sum(1 for s in statuses if s == "not_assessed"),
                "excluded": 0,
            },
        })

    completion_rate = round((completed_drives / total_drives) * 100, 1) if total_drives else 0.0

    return {
        "total_drives": total_drives,
        "completed_drives": completed_drives,
        "completion_rate": completion_rate,
        "drive_summaries": drive_summaries,
        "competency_results": competency_results,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


@router.get("/mock-drive/{drive_id}/results", response_model=dict)
def get_mock_drive_results(
    drive_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Per-candidate results for a specific Mock Drive.

    Rounds, overall status and competency summaries are derived from the
    authoritative AssessmentContext / AssessmentSession / AssessmentRound records
    and the competency scoring service. Scores are reported exactly as persisted;
    nothing is rescaled or invented.
    """
    check_admin(current_user)

    from app.services.mock_drive_service import (
        _enabled_rounds_in_order,
        _roster_rounds_for_session,
    )
    from app.services.competency_scoring_service import score_session_competencies

    mock_drive = db.query(MockDrive).filter(MockDrive.id == drive_id).first()
    if not mock_drive:
        raise HTTPException(status_code=404, detail="Mock Drive not found")
    if mock_drive.status not in ("published", "active", "completed"):
        raise HTTPException(status_code=400, detail="Mock Drive must be published to view results")

    enabled = _enabled_rounds_in_order(mock_drive)

    contexts = (
        db.query(AssessmentContext)
        .filter(
            AssessmentContext.mock_drive_id == drive_id,
            AssessmentContext.purpose == "mock_drive",
        )
        .order_by(AssessmentContext.id)
        .all()
    )

    candidate_results = []
    for ctx in contexts:
        user = db.query(User).filter(User.id == ctx.student_id).first()
        session = (
            db.query(AssessmentSession)
            .filter(AssessmentSession.context_id == ctx.id)
            .order_by(AssessmentSession.id.desc())
            .first()
        )
        if session is None:
            continue

        rounds = _roster_rounds_for_session(db, session, enabled)
        completed_rounds = [r for r in rounds if r["status"] in ("completed", "expired")]

        # Read-only safeguard: only score when the context already has a pinned
        # snapshot, so the scoring service never backfills persisted state.
        scoring = score_session_competencies(db, session) if ctx.blueprint_snapshot else None

        comp_summary = []
        if scoring:
            for comp in scoring.get("competencies", []):
                comp_summary.append({
                    "competency_id": str(comp["competency_id"]),
                    "competency_name": comp["competency_name"],
                    "avg_score": comp["normalized_score"],
                    "evidence_count": comp["evidence_count"],
                    "max_evidence": comp["evidence_count"],
                    "status_distribution": {
                        "assessed": 1 if comp["status"] == "assessed" else 0,
                        "not_assessed": 1 if comp["status"] == "not_assessed" else 0,
                    },
                    "missing_competencies": (
                        [comp["competency_name"]] if comp["status"] != "assessed" else []
                    ),
                })

        if scoring:
            overall_status = scoring["overall_score_status"]
            overall_score = scoring["overall_score"]
            missing_competency_names = scoring["missing_competencies"]
        else:
            overall_status = "unavailable"
            overall_score = None
            missing_competency_names = []

        candidate_results.append({
            "candidate_id": ctx.student_id,
            "candidate_name": user.name if user else "Unknown",
            "overall_status": overall_status,
            "overall_score": overall_score,
            "completed_rounds": len(completed_rounds),
            "round_details": [
                {
                    "round_id": None,
                    "round_type": r["round_type"],
                    "status": r["status"],
                    "score": r["score"],
                    "max_score": r["max_score"],
                }
                for r in rounds
            ],
            "competency_summary": comp_summary,
            "missing_competency_names": missing_competency_names,
        })

    return {
        "drive_id": mock_drive.id,
        "company_name": mock_drive.company_name,
        "target_role": mock_drive.target_role,
        "total_candidates": len(candidate_results),
        "candidate_results": candidate_results,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


@router.get("/mock-drive/{drive_id}/evidence-coverage", response_model=dict)
def get_mock_drive_evidence_coverage(
    drive_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Per-competency evidence coverage for a specific Mock Drive.

    Derived from the pinned blueprint snapshot and the competency scoring service.
    No competency score is persisted or fabricated.
    """
    check_admin(current_user)

    from app.services.competency_mapping_service import (
        configured_competencies,
        competency_identifier,
    )
    from app.services.competency_scoring_service import score_session_competencies

    mock_drive = db.query(MockDrive).filter(MockDrive.id == drive_id).first()
    if not mock_drive:
        raise HTTPException(status_code=404, detail="Mock Drive not found")

    contexts = (
        db.query(AssessmentContext)
        .filter(
            AssessmentContext.mock_drive_id == drive_id,
            AssessmentContext.purpose == "mock_drive",
        )
        .all()
    )

    coverage_map: dict = {}
    snapshot = None
    for ctx in contexts:
        if snapshot is None and ctx.blueprint_snapshot:
            snapshot = ctx.blueprint_snapshot
        # Read-only safeguard: never score a context without a pinned snapshot.
        if not ctx.blueprint_snapshot:
            continue
        session = (
            db.query(AssessmentSession)
            .filter(AssessmentSession.context_id == ctx.id)
            .order_by(AssessmentSession.id.desc())
            .first()
        )
        if session is None:
            continue
        scoring = score_session_competencies(db, session)
        for comp in scoring.get("competencies", []):
            entry = coverage_map.setdefault(comp["competency_id"], {
                "competency_name": comp["competency_name"],
                "weight_pct": comp.get("weight_pct"),
                "evidence_count": 0,
                "assessed_count": 0,
                "not_assessed_count": 0,
                "evidence_types": set(),
                "sources": set(),
            })
            entry["evidence_count"] += comp["evidence_count"]
            if comp["status"] == "assessed":
                entry["assessed_count"] += 1
            else:
                entry["not_assessed_count"] += 1
            entry["evidence_types"].update(comp.get("evidence_types", []))
            entry["sources"].update(comp.get("sources", []))

    # Include configured blueprint competencies that have no scored evidence.
    for comp in configured_competencies(snapshot):
        cid = competency_identifier(comp)
        if cid and cid not in coverage_map:
            coverage_map[cid] = {
                "competency_name": str(comp.get("name", "")).strip(),
                "weight_pct": comp.get("weight_pct", 0),
                "evidence_count": 0,
                "assessed_count": 0,
                "not_assessed_count": 0,
                "evidence_types": set(),
                "sources": set(),
            }

    coverage_results = []
    for cid, data in sorted(coverage_map.items(), key=lambda x: str(x[0])):
        total = data["assessed_count"] + data["not_assessed_count"]
        coverage_rate = round((data["assessed_count"] / total * 100), 1) if total > 0 else 0.0
        coverage_results.append({
            "competency_id": str(cid),
            "competency_name": data["competency_name"],
            "weight_pct": data["weight_pct"],
            "evidence_count": data["evidence_count"],
            "assessed_count": data["assessed_count"],
            "not_assessed_count": data["not_assessed_count"],
            "coverage_rate": coverage_rate,
            "evidence_types": sorted(data["evidence_types"]),
            "sources": sorted(data["sources"]),
        })

    return {
        "drive_id": mock_drive.id,
        "company_name": mock_drive.company_name,
        "target_role": mock_drive.target_role,
        "total_competencies": len(coverage_results),
        "coverage_results": coverage_results,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


# ── TPO Analytics: comprehensive read-only overview ──────────────────────
def _round_label(rt):
    return {"aptitude": "Aptitude", "coding": "Coding", "interview": "Interview"}.get(rt, rt)


@router.get("/analytics/overview", response_model=dict)
def get_analytics_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    period: str = Query("all", pattern="^(7|30|90|all)$"),
    company: Optional[str] = None,
    role: Optional[str] = None,
    drive_status: Optional[str] = None,
    round_type: Optional[str] = None,
) -> dict:
    """Comprehensive read-only TPO analytics.

    Aggregates real persisted records across published/active/completed drives.
    Drafts are excluded. Competency scores are derived only from the
    authoritative scoring service and only for contexts that already have a
    pinned blueprint snapshot (read-only safeguard). ``passed_candidates`` is
    always ``None``: EDI5 persists no authoritative pass/hire outcome, and this
    endpoint will not invent one.
    """
    check_admin(current_user)

    from app.models.mock_drive import MockDrive as _MD
    from app.services.mock_drive_service import _enabled_rounds_in_order, _roster_rounds_for_session
    from app.services.competency_scoring_service import score_session_competencies

    # ── Drive filter base (drafts excluded per policy) ──────────────────
    drive_q = db.query(_MD).filter(_MD.status.in_(("published", "active", "completed")))
    if company:
        drive_q = drive_q.filter(_MD.company_name == company)
    if role:
        drive_q = drive_q.filter(_MD.target_role == role)
    if drive_status:
        drive_q = drive_q.filter(_MD.status == drive_status)
    drives = drive_q.order_by(_MD.id).all()

    # Period cutoff (relative to now, UTC).
    cutoff = None
    if period != "all":
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=int(period))

    def _in_period(dt):
        if cutoff is None or dt is None:
            return True
        return dt.replace(tzinfo=None) >= cutoff

    # ── Filter option catalogs (from real data) ─────────────────────────
    all_drives = db.query(_MD).filter(_MD.status.in_(("published", "active", "completed"))).all()
    companies = sorted({d.company_name for d in all_drives if d.company_name})
    roles = sorted({d.target_role for d in all_drives if d.target_role})
    statuses = sorted({d.status for d in all_drives if d.status})

    # ── Per-drive aggregation ───────────────────────────────────────────
    drive_rows = []
    enrolled_total = 0
    completed_total = 0
    activity = {}  # date -> {enrolled, completed}
    round_stats = {}  # round_type -> {enrolled, completed, scores[]}
    funnel = {"enrolled": 0, "aptitude": 0, "coding": 0, "interview": 0}
    # department -> competency_id -> {name, weight, scores[], evidence}
    dept_comp = defaultdict(lambda: defaultdict(lambda: {"name": None, "weight": None, "scores": [], "evidence": 0, "assessed": 0, "total": 0}))
    competency_index = {}  # cid -> {name, scores[], evidence, assessed, total, departments}
    enabled_round_keys = set()
    competency_coverage = {
        "eligible_contexts": 0,
        "contexts_without_session": 0,
        "contexts_without_snapshot": 0,
        "contexts_without_competencies": 0,
        "contexts_without_countable_evidence": 0,
        "final_scored_contexts": 0,
        "provisional_scored_contexts": 0,
        "scoring_errors": 0,
        "mapping_statuses": {
            "pending": 0, "failed": 0, "completed": 0,
            "not_applicable": 0, "untracked": 0,
        },
    }

    for drive in drives:
        enabled = _enabled_rounds_in_order(drive)
        enabled_round_keys.update(enabled)

        contexts = (
            db.query(AssessmentContext)
            .filter(
                AssessmentContext.mock_drive_id == drive.id,
                AssessmentContext.purpose == "mock_drive",
            )
            .all()
        )
        if cutoff is not None:
            contexts = [c for c in contexts if _in_period(c.created_at)]
        competency_coverage["eligible_contexts"] += len(contexts)
        for ctx in contexts:
            mapping_state = ctx.competency_mapping_status
            mapping_key = mapping_state if mapping_state in competency_coverage["mapping_statuses"] else "untracked"
            competency_coverage["mapping_statuses"][mapping_key] += 1
        if not contexts:
            drive_rows.append({
                "drive_id": drive.id, "company_name": drive.company_name,
                "target_role": drive.target_role, "status": drive.status,
                "enrolled": 0, "completed": 0, "completion_rate": 0.0,
                "round_avg": {}, "enabled_rounds": enabled,
            })
            continue

        session_ids = []
        drive_completed = 0
        for ctx in contexts:
            enrolled_total += 1
            funnel["enrolled"] += 1
            if ctx.created_at:
                key = ctx.created_at.strftime("%Y-%m-%d")
                activity.setdefault(key, {"enrolled": 0, "completed": 0})["enrolled"] += 1

            sess = (
                db.query(AssessmentSession)
                .filter(AssessmentSession.context_id == ctx.id)
                .order_by(AssessmentSession.id.desc())
                .first()
            )
            if sess is None:
                competency_coverage["contexts_without_session"] += 1
                continue
            session_ids.append((sess, ctx))
            if ctx.status == "completed":
                drive_completed += 1
                completed_total += 1
                if ctx.completed_at:
                    key = ctx.completed_at.strftime("%Y-%m-%d")
                    activity.setdefault(key, {"enrolled": 0, "completed": 0})["completed"] += 1

        # round performance + funnel per drive
        for sess, ctx in session_ids:
            rounds = _roster_rounds_for_session(db, sess, enabled)
            completed_types = set()
            for r in rounds:
                rt = r["round_type"]
                if rt == "interview":
                    # canonical interview key
                    key = r.get("round", "interview")
                    label_key = "interview"
                else:
                    label_key = rt
                st = round_stats.setdefault(label_key, {"enrolled": 0, "completed": 0, "scores": []})
                st["enrolled"] += 1
                if r["status"] in ("completed", "expired"):
                    st["completed"] += 1
                    completed_types.add(label_key)
                    if r["score"] is not None:
                        st["scores"].append(r["score"])
            if "aptitude" in completed_types:
                funnel["aptitude"] += 1
            if "coding" in completed_types:
                funnel["coding"] += 1
            if "interview" in completed_types:
                funnel["interview"] += 1

            # competency scoring (read-only safeguard)
            if not ctx.blueprint_snapshot:
                competency_coverage["contexts_without_snapshot"] += 1
            else:
                try:
                    scoring = score_session_competencies(db, sess)
                    if (scoring.get("scoring_error") or "").startswith("no_configured_competencies"):
                        competency_coverage["contexts_without_competencies"] += 1
                    elif scoring.get("scoring_error"):
                        competency_coverage["scoring_errors"] += 1
                    competencies = scoring.get("competencies", [])
                    if competencies and not any((comp.get("evidence_count") or 0) > 0 for comp in competencies):
                        competency_coverage["contexts_without_countable_evidence"] += 1
                    if scoring.get("overall_score_status") == "final":
                        competency_coverage["final_scored_contexts"] += 1
                    elif scoring.get("overall_score_status") == "provisional":
                        competency_coverage["provisional_scored_contexts"] += 1
                    for comp in scoring.get("competencies", []):
                        cid = comp["competency_id"]
                        dept = None
                        prof = (
                            db.query(StudentProfile)
                            .filter(StudentProfile.user_id == ctx.student_id)
                            .first()
                        )
                        if prof is not None:
                            dept = prof.department
                        ci = competency_index.setdefault(cid, {
                            "name": comp["competency_name"], "scores": [],
                            "evidence": 0, "assessed": 0, "total": 0, "departments": defaultdict(list),
                        })
                        ci["total"] += 1
                        ci["evidence"] += comp["evidence_count"]
                        if comp["status"] == "assessed":
                            ci["assessed"] += 1
                        if comp["normalized_score"] is not None:
                            ci["scores"].append(comp["normalized_score"])
                            if dept:
                                ci["departments"][dept].append(comp["normalized_score"])
                        if dept:
                            dc = dept_comp[dept][cid]
                            dc["name"] = comp["competency_name"]
                            dc["weight"] = comp.get("weight_pct")
                            dc["total"] += 1
                            dc["evidence"] += comp["evidence_count"]
                            if comp["status"] == "assessed":
                                dc["assessed"] += 1
                            if comp["normalized_score"] is not None:
                                dc["scores"].append(comp["normalized_score"])
                except Exception:
                    competency_coverage["scoring_errors"] += 1
                    logger.exception(
                        "Skipped competency analytics scoring for context %s, session %s",
                        ctx.id,
                        sess.id,
                    )

        rate = round(drive_completed / len(contexts) * 100, 1) if contexts else 0.0
        drive_rows.append({
            "drive_id": drive.id, "company_name": drive.company_name,
            "target_role": drive.target_role, "status": drive.status,
            "enrolled": len(contexts), "completed": drive_completed,
            "completion_rate": rate, "enabled_rounds": enabled,
        })

    # Attach round averages per drive row (from round_stats is global; recompute per drive)
    # For simplicity, round_avg left as global in round_performance; drive rows carry counts only.

    # ── Build round performance output ──────────────────────────────────
    round_performance = []
    for rt, st in round_stats.items():
        scores = st["scores"]
        round_performance.append({
            "round_type": rt,
            "round_label": _round_label(rt),
            "enrolled": st["enrolled"],
            "completed": st["completed"],
            "completion_rate": round(st["completed"] / st["enrolled"] * 100, 1) if st["enrolled"] else 0.0,
            "avg_score": round(sum(scores) / len(scores), 2) if scores else None,
            "score_count": len(scores),
        })

    # ── Activity trend (daily buckets across the period) ────────────────
    activity_trend = [{"date": d, "enrolled": v["enrolled"], "completed": v["completed"]}
                      for d, v in sorted(activity.items())]

    # ── Funnel ──────────────────────────────────────────────────────────
    total_enrolled = funnel["enrolled"]
    def _conv(n):
        return round(n / total_enrolled * 100, 1) if total_enrolled else 0.0
    funnel_stages = []
    if total_enrolled:
        funnel_stages.append(
            {"stage": "Enrolled", "count": funnel["enrolled"], "conversion": 100.0}
        )
        if "aptitude" in enabled_round_keys:
            funnel_stages.append({"stage": "Aptitude completed", "count": funnel["aptitude"], "conversion": _conv(funnel["aptitude"])})
        if "coding" in enabled_round_keys:
            funnel_stages.append({"stage": "Coding completed", "count": funnel["coding"], "conversion": _conv(funnel["coding"])})
        if {"interview", "technical_interview", "hr_interview"} & set(enabled_round_keys):
            funnel_stages.append({"stage": "Interview completed", "count": funnel["interview"], "conversion": _conv(funnel["interview"])})
    # No "Hired/Passed" stage: EDI5 persists no authoritative outcome.

    # ── Competency insights ─────────────────────────────────────────────
    competency_insights = []
    for cid, ci in competency_index.items():
        scores = ci["scores"]
        top_dept = None
        if ci["departments"]:
            best = max(ci["departments"].items(), key=lambda kv: (len(kv[1]), sum(kv[1]) / len(kv[1]) if kv[1] else 0))
            if best[1]:
                top_dept = best[0]
        competency_insights.append({
            "competency_id": str(cid),
            "competency_name": ci["name"],
            "avg_score": round(sum(scores) / len(scores), 2) if scores else None,
            "evidence_count": ci["evidence"],
            "assessed": ci["assessed"],
            "total": ci["total"],
            "coverage_rate": round(ci["assessed"] / ci["total"] * 100, 1) if ci["total"] else 0.0,
            "top_department": top_dept,
        })
    competency_insights.sort(key=lambda x: x["competency_name"] or "")

    # ── Competency weight by department ─────────────────────────────────
    departments = sorted(dept_comp.keys())
    dept_payload = []
    for dept in departments:
        comps = []
        for cid, dc in dept_comp[dept].items():
            comps.append({
                "competency_id": str(cid),
                "competency_name": dc["name"],
                "weight_pct": dc["weight"],
                "avg_score": round(sum(dc["scores"]) / len(dc["scores"]), 2) if dc["scores"] else None,
                "evidence_count": dc["evidence"],
            })
        comps.sort(key=lambda x: x["competency_name"] or "")
        dept_payload.append({"department": dept, "competencies": comps})

    # ── KPIs ────────────────────────────────────────────────────────────
    completion_rate = round(completed_total / enrolled_total * 100, 1) if enrolled_total else 0.0
    kpis = {
        "total_drives": len(drives),
        "enrolled_candidates": enrolled_total,
        "completion_rate": completion_rate,
        # Honest unavailable: no authoritative pass outcome is persisted in EDI5.
        "passed_candidates": None,
        "passed_candidates_available": False,
    }

    return {
        "kpis": kpis,
        "filters": {
            "companies": companies, "roles": roles, "drive_statuses": statuses,
            "round_types": sorted({_round_label(rt) for rt in enabled_round_keys}),
            "departments": departments,
            "periods": ["7", "30", "90", "all"],
        },
        "activity_trend": activity_trend,
        "round_performance": round_performance,
        "funnel": {"stages": funnel_stages},
        "competency_by_department": {"departments": dept_payload, "available": bool(dept_payload)},
        "competency_insights": competency_insights,
        "competency_coverage": competency_coverage,
        "drives": drive_rows,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


# ── TPO Readiness Analytics (EDI5, read-only) ──────────────────────────

_READINESS_SCORE_DEFINITION = (
    "Competency overall score (0-100) from the authoritative competency scoring "
    "service (score_session_competencies, scoring policy d1-v1), computed from each "
    "session's pinned blueprint snapshot and persisted evidence mappings. Eligible "
    "attempts are completed mock-drive candidate contexts whose score is available "
    "(final or provisional). Unavailable scores are excluded, never treated as zero."
)

_ATTEMPT_IMPROVEMENT_DEFINITION = (
    "Change in competency readiness score (0-100) between each candidate's earliest "
    "and latest eligible completed attempt under the same scoring policy. "
    "Descriptive comparison only — it does not attribute the change to completing "
    "multiple mocks."
)


@router.get("/readiness/overview", response_model=dict)
def get_readiness_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    period: str = Query("all", pattern="^(7|30|90|all)$"),
    company: Optional[str] = None,
    role: Optional[str] = None,
    drive_status: Optional[str] = None,
) -> dict:
    """Read-only readiness analytics for the TPO Readiness Analytics page.

    Aggregates competency readiness scores from persisted, completed mock-drive
    attempts scoped by the same drive filters as ``/analytics/overview``. The
    response contains aggregates only — no candidate identifiers or names. EDI5
    persists no placement/offer outcomes and defines no institutional readiness
    threshold, so those metrics are returned as explicitly unavailable rather
    than invented. Scoring reuses the read-only competency scoring service and
    fails closed on error.
    """
    check_admin(current_user)

    from app.models.mock_drive import MOCK_DRIVE_STATUSES, MockDrive as _MD
    from app.services.competency_scoring_service import (
        SCORING_POLICY_VERSION,
        _NON_COUNTABLE_CODING_STATUSES,
        score_session_competencies,
    )

    # ── Drive filter base (drafts excluded per policy, same as overview) ──
    drive_q = db.query(_MD).filter(_MD.status.in_(("published", "active", "completed")))
    if company:
        drive_q = drive_q.filter(_MD.company_name == company)
    if role:
        drive_q = drive_q.filter(_MD.target_role == role)
    if drive_status:
        drive_q = drive_q.filter(_MD.status == drive_status)
    drives = drive_q.order_by(_MD.id).all()

    # Period cutoff (relative to now, UTC) — same convention as overview.
    cutoff = None
    if period != "all":
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=int(period))

    def _in_period(dt):
        if cutoff is None or dt is None:
            return True
        return dt.replace(tzinfo=None) >= cutoff

    # ── Filter option catalogs (from real data) ─────────────────────────
    all_drives = db.query(_MD).filter(_MD.status.in_(("published", "active", "completed"))).all()
    companies = sorted({d.company_name for d in all_drives if d.company_name})
    roles = sorted({d.target_role for d in all_drives if d.target_role})
    statuses = sorted({d.status for d in all_drives if d.status})

    dept_cache: dict[int, str] = {}

    def _department_of(student_id: int) -> str:
        if student_id in dept_cache:
            return dept_cache[student_id]
        prof = (
            db.query(StudentProfile)
            .filter(StudentProfile.user_id == student_id)
            .first()
        )
        dept = prof.department if prof is not None and prof.department else "Unspecified"
        dept_cache[student_id] = dept
        return dept

    # ── Batched reads: one query for every context of the in-scope drives,
    #    one for every session on those contexts (no per-drive N+1). ───────
    drive_ids = [d.id for d in drives]
    scoped_contexts: List[AssessmentContext] = []
    if drive_ids:
        scoped_contexts = (
            db.query(AssessmentContext)
            .filter(
                AssessmentContext.mock_drive_id.in_(drive_ids),
                AssessmentContext.purpose == "mock_drive",
            )
            .order_by(AssessmentContext.id)
            .all()
        )
        if cutoff is not None:
            scoped_contexts = [c for c in scoped_contexts if _in_period(c.created_at)]

    contexts_by_drive: dict[int, list] = defaultdict(list)
    for _ctx in scoped_contexts:
        contexts_by_drive[_ctx.mock_drive_id].append(_ctx)

    latest_session_by_ctx: dict[int, AssessmentSession] = {}
    sessions_on_scope: List[AssessmentSession] = []
    _context_ids = [c.id for c in scoped_contexts]
    if _context_ids:
        for _sess in (
            db.query(AssessmentSession)
            .filter(AssessmentSession.context_id.in_(_context_ids))
            .order_by(AssessmentSession.id)
            .all()
        ):
            sessions_on_scope.append(_sess)
            _prev = latest_session_by_ctx.get(_sess.context_id)
            if _prev is None or _sess.id > _prev.id:
                latest_session_by_ctx[_sess.context_id] = _sess

    # ── Per-drive pass: collect eligible scored attempts (aggregates only) ─
    attempts = []  # scored attempts used by readiness metrics
    skill_gap_attempts = []  # completed configured attempts, even without scores
    contexts_examined = 0
    completed_contexts = 0
    contexts_with_snapshot = 0
    contexts_with_configured_competencies = 0
    contexts_with_evidence_mappings = 0
    students_with_contexts = set()
    students_with_completed_contexts = set()
    skipped_scoring_errors = 0
    drive_rows = []

    # Follow-up counters (Section 2 "Scoring Follow-up"). Each completed
    # context that cannot produce a usable readiness score is classified into
    # exactly one reason so the TPO can act on it. These are context counts
    # (one per completed assessment attempt), never mixed with candidate counts.
    followup_missing_snapshot = 0
    followup_no_competencies = 0
    followup_no_mappings = 0
    followup_no_usable_score = 0
    followup_scoring_error = 0

    # Drive-activity accumulators. Operational counts only — no scores, so
    # they work even when there is no competency evidence at all.
    activity_rows = []
    participant_statuses: dict[int, set] = defaultdict(set)

    for drive in drives:
        ctx_rows = contexts_by_drive.get(drive.id, [])

        drive_enrolled = len(ctx_rows)
        drive_completed = 0
        drive_scores: list[float] = []
        drive_scored_students: set[int] = set()

        # Mutually exclusive participant buckets for this drive. A student with
        # repeated attempts is one participant, never two.
        drive_participants: dict[int, set] = defaultdict(set)
        for ctx in ctx_rows:
            if ctx.student_id is None:
                continue
            drive_participants[ctx.student_id].add(ctx.status)
            participant_statuses[ctx.student_id].add(ctx.status)

        completed_p = sum(1 for st in drive_participants.values() if "completed" in st)
        in_progress_p = sum(
            1 for st in drive_participants.values()
            if "completed" not in st and "active" in st
        )
        not_started_p = len(drive_participants) - completed_p - in_progress_p

        for ctx in ctx_rows:
            contexts_examined += 1
            students_with_contexts.add(ctx.student_id)
            if ctx.status != "completed":
                continue
            drive_completed += 1
            completed_contexts += 1
            # Distinct candidates with at least one completed attempt. Tracked
            # separately from students_with_contexts (which also counts
            # in-progress and not-started contexts) so "needing assessment"
            # never counts a candidate who has not completed anything.
            if ctx.student_id is not None:
                students_with_completed_contexts.add(ctx.student_id)

            sess = latest_session_by_ctx.get(ctx.id)
            has_snapshot = bool(ctx.blueprint_snapshot)
            if has_snapshot:
                contexts_with_snapshot += 1
            if sess is None or not has_snapshot:
                # Completed attempt that cannot even be evaluated: no pinned
                # snapshot (or no session). Classified as followed-up.
                if not has_snapshot:
                    followup_missing_snapshot += 1
                continue
            try:
                scoring = score_session_competencies(db, sess)
            except Exception:
                skipped_scoring_errors += 1
                followup_scoring_error += 1
                continue  # scoring fails closed; never fabricate
            required_count = scoring.get("required_competency_count") or 0
            if required_count:
                contexts_with_configured_competencies += 1
            has_mappings = any(
                (competency.get("evidence_count") or 0) > 0
                for competency in scoring.get("competencies", [])
            )
            if has_mappings:
                contexts_with_evidence_mappings += 1
            snapshot = ctx.blueprint_snapshot or {}
            configured_rounds = snapshot.get("enabled_rounds")
            if configured_rounds is None:
                configured_rounds = [
                    item.get("round_type")
                    for item in (snapshot.get("blueprint_data") or {}).get("rounds", [])
                    if isinstance(item, dict)
                ]
            supported_types = {
                round_type for round_type in configured_rounds
                if round_type in {"aptitude", "coding"}
            }
            if supported_types:
                skill_gap_attempts.append({
                    "student_id": ctx.student_id,
                    "competencies": scoring.get("competencies", []),
                    "assessment_types": supported_types,
                })
            overall = scoring.get("overall_score")
            if overall is None:
                # Classify the follow-up reason for this completed attempt.
                # The scoring service reports "no_configured_competencies" via
                # scoring_error; surface that specific reason as configuration
                # follow-up rather than a generic scoring failure.
                scoring_error = scoring.get("scoring_error")
                if not required_count:
                    followup_no_competencies += 1
                elif scoring_error:
                    followup_scoring_error += 1
                elif not has_mappings:
                    followup_no_mappings += 1
                else:
                    followup_no_usable_score += 1
                continue
            attempts.append({
                "student_id": ctx.student_id,
                "drive_id": drive.id,
                "score": float(overall),
                "score_status": scoring.get("overall_score_status"),
                "at": ctx.completed_at or ctx.created_at,
                "competencies": scoring.get("competencies", []),
            })
            drive_scores.append(float(overall))
            drive_scored_students.add(ctx.student_id)

        # Enrolled/Completed are distinct candidates (participants); raw
        # attempt-context counts are reported separately as contexts /
        # completed_contexts. completion_rate is null, never 0, at zero
        # denominator so no UI can render a fabricated 0%.
        rate = (
            round(completed_p / len(drive_participants) * 100, 1)
            if drive_participants else None
        )
        drive_rows.append({
            "drive_id": drive.id,
            "company_name": drive.company_name,
            "target_role": drive.target_role,
            "status": drive.status,
            "enrolled": len(drive_participants),
            "completed": completed_p,
            "contexts": drive_enrolled,
            "completed_contexts": drive_completed,
            "completion_rate": rate,
            "scored_attempts": len(drive_scores),
            "scored_candidates": len(drive_scored_students),
            "avg_readiness": (
                round(sum(drive_scores) / len(drive_scores), 2) if drive_scores else None
            ),
        })

        # Completion analytics for the same drive, over distinct participants.
        # completion_rate is null (not 0) when nobody is enrolled.
        activity_rows.append({
            "drive_id": drive.id,
            "company_name": drive.company_name,
            "target_role": drive.target_role,
            "status": drive.status,
            "contexts": drive_enrolled,
            "participants": len(drive_participants),
            "completed_participants": completed_p,
            "in_progress_participants": in_progress_p,
            "not_started_participants": not_started_p,
            "completed_contexts": sum(1 for c in ctx_rows if c.status == "completed"),
            "active_contexts": sum(1 for c in ctx_rows if c.status == "active"),
            "cancelled_contexts": sum(1 for c in ctx_rows if c.status == "cancelled"),
            "completion_rate": (
                round(completed_p / len(drive_participants) * 100, 1)
                if drive_participants else None
            ),
        })

    # ── Historical assessment evidence (EDI5 Section 2) ─────────────────
    # Three categories of persisted results, each with its own authoritative
    # scale and never averaged across types:
    #   aptitude   graded aptitude_attempts  -> accuracy 0-100
    #   coding     countable coding_submissions + persisted round score 0-1
    #   interview  InterviewTurn.final_score  -> mean of scored turns 0-1
    # A completed round with no persisted result is reported as "no result"
    # (rounds_with_results < completed_rounds) and is never counted as a 0.
    _ASSESSMENT_TYPES = ("aptitude", "coding", "interview")
    _TYPE_META = {
        "aptitude": {
            "label": "Aptitude",
            "min": 0, "max": 100, "unit": "accuracy %",
            "scale": "accuracy 0-100 (correct graded responses / graded responses)",
        },
        "coding": {
            "label": "Coding",
            "min": 0, "max": 1, "unit": "score",
            "scale": "final coding score 0-1 (persisted by finalize_coding_round)",
        },
        "interview": {
            "label": "Interview",
            "min": 0, "max": 1, "unit": "score",
            "scale": "mean interview turn score 0-1 (InterviewTurn.final_score)",
        },
    }
    _TYPE_DEFINITION = {
        "aptitude": (
            "Accuracy = correct graded aptitude responses / graded responses x 100, "
            "computed per round from aptitude_attempts where is_correct is recorded. "
            "A completed aptitude round with no graded response has no result and is "
            "excluded (never zeroed); ungraded or missing responses are excluded from "
            "the denominator, never counted as wrong."
        ),
        "coding": (
            "Persisted round score (0-1) written by finalize_coding_round, counted only "
            "for rounds with at least one countable submission (score recorded and "
            "status not in {internal_error, running}, per scoring policy d1-v1). A "
            "completed coding round without a countable submission has no result."
        ),
        "interview": (
            "Mean of InterviewTurn.final_score (0-1) over the turns of the candidate's "
            "latest completed interview round per assessment session, so repeated "
            "rounds on one session are not double counted. Completed interview rounds "
            "whose session has no scored turn have no result."
        ),
    }

    ctx_by_id = {c.id: c for c in scoped_contexts}
    session_by_id = {s.id: s for s in sessions_on_scope}

    rounds_by_type: dict[str, list[dict]] = {"aptitude": [], "coding": [], "interview": []}
    if session_by_id:
        for _rnd in (
            db.query(AssessmentRound)
            .filter(
                AssessmentRound.session_id.in_(list(session_by_id)),
                AssessmentRound.status == "completed",
            )
            .order_by(AssessmentRound.id)
            .all()
        ):
            _sess = session_by_id.get(_rnd.session_id)
            _ctx = ctx_by_id.get(_sess.context_id) if _sess else None
            if _sess is None or _ctx is None or _rnd.round_type not in rounds_by_type:
                continue
            # Period filter on the round's own completion time, falling back to
            # its session / context event times — same event convention as the
            # rest of the page.
            _when = (
                _rnd.completed_at
                or _sess.completed_at
                or _ctx.completed_at
                or _ctx.created_at
            )
            if not _in_period(_when):
                continue
            rounds_by_type[_rnd.round_type].append({
                "round_id": _rnd.id,
                "session_id": _sess.id,
                "student_id": _sess.user_id,
                "score": float(_rnd.score) if _rnd.score is not None else None,
                "at": _when,
            })

    # Batched evidence reads: one grouped query per assessment type.
    apt_round_ids = [r["round_id"] for r in rounds_by_type["aptitude"]]
    apt_stats: dict[int, dict] = {}
    if apt_round_ids:
        for _rid, _total, _correct in (
            db.query(
                AptitudeAttempt.round_id,
                func.count(AptitudeAttempt.id),
                func.sum(case((AptitudeAttempt.is_correct.is_(True), 1), else_=0)),
            )
            .filter(
                AptitudeAttempt.round_id.in_(apt_round_ids),
                AptitudeAttempt.is_correct.isnot(None),
            )
            .group_by(AptitudeAttempt.round_id)
            .all()
        ):
            apt_stats[int(_rid)] = {
                "responses": int(_total or 0),
                "correct": int(_correct or 0),
            }

    cod_round_ids = [r["round_id"] for r in rounds_by_type["coding"]]
    cod_stats: dict[int, dict] = {}
    if cod_round_ids:
        for _sub in (
            db.query(CodingSubmission)
            .filter(CodingSubmission.round_id.in_(cod_round_ids))
            .all()
        ):
            _st = cod_stats.setdefault(_sub.round_id, {"submissions": 0, "countable": 0})
            _st["submissions"] += 1
            if _sub.score is not None and (
                not _sub.status or _sub.status not in _NON_COUNTABLE_CODING_STATUSES
            ):
                _st["countable"] += 1

    iv_rounds = rounds_by_type["interview"]
    iv_turns_by_session: dict[int, dict] = {}
    if iv_rounds:
        _iv_session_ids = sorted({r["session_id"] for r in iv_rounds})
        iv_sessions = (
            db.query(InterviewSession)
            .filter(InterviewSession.session_id.in_(_iv_session_ids))
            .all()
        )
        if iv_sessions:
            turns_by_interview: dict[int, dict] = {}
            for _iid, _scored, _total, _sum in (
                db.query(
                    InterviewTurn.interview_id,
                    func.sum(case((InterviewTurn.final_score.isnot(None), 1), else_=0)),
                    func.count(InterviewTurn.id),
                    func.coalesce(func.sum(InterviewTurn.final_score), 0.0),
                )
                .filter(
                    InterviewTurn.interview_id.in_([i.id for i in iv_sessions])
                )
                .group_by(InterviewTurn.interview_id)
                .all()
            ):
                turns_by_interview[int(_iid)] = {
                    "scored": int(_scored or 0),
                    "total": int(_total or 0),
                    "sum": float(_sum or 0.0),
                }
            for _ivs in iv_sessions:
                _t = turns_by_interview.get(_ivs.id, {"scored": 0, "total": 0, "sum": 0.0})
                _agg = iv_turns_by_session.setdefault(
                    _ivs.session_id, {"scored": 0, "total": 0, "sum": 0.0}
                )
                _agg["scored"] += _t["scored"]
                _agg["total"] += _t["total"]
                _agg["sum"] += _t["sum"]

    # Derive usable scored results per type (attempts with results vs rounds
    # with a valid score are reported separately).
    scored_by_type: dict[str, list[dict]] = {"aptitude": [], "coding": [], "interview": []}
    rounds_with_results = {"aptitude": 0, "coding": 0, "interview": 0}

    for _r in rounds_by_type["aptitude"]:
        _st = apt_stats.get(_r["round_id"])
        if not _st or not _st["responses"]:
            continue
        rounds_with_results["aptitude"] += 1
        scored_by_type["aptitude"].append({
            **_r,
            "score": round(_st["correct"] / _st["responses"] * 100, 1),
            "responses": _st["responses"],
            "correct": _st["correct"],
        })

    for _r in rounds_by_type["coding"]:
        _st = cod_stats.get(_r["round_id"])
        if not _st or not _st["submissions"]:
            continue
        rounds_with_results["coding"] += 1
        if not _st["countable"] or _r["score"] is None:
            continue  # submitted-but-not-countable has no usable score
        scored_by_type["coding"].append({**_r, "submissions": _st["submissions"]})

    _iv_latest: dict[int, dict] = {}
    for _r in iv_rounds:
        _agg = iv_turns_by_session.get(_r["session_id"])
        if not _agg or not _agg["total"]:
            continue
        rounds_with_results["interview"] += 1
        _prev = _iv_latest.get(_r["session_id"])
        if _prev is None or _r["round_id"] > _prev["round_id"]:
            _iv_latest[_r["session_id"]] = _r
    for _sess_id, _r in _iv_latest.items():
        _agg = iv_turns_by_session[_sess_id]
        if not _agg["scored"]:
            continue  # turns exist but none carries a final_score
        scored_by_type["interview"].append({
            **_r,
            "score": round(_agg["sum"] / _agg["scored"], 3),
            "turns": _agg["scored"],
        })

    def _assessment_component(ctype: str) -> dict:
        meta = _TYPE_META[ctype]
        completed = len(rounds_by_type[ctype])
        with_results = rounds_with_results[ctype]
        scored = scored_by_type[ctype]
        scores = [e["score"] for e in scored]
        block = {
            "key": ctype,
            "label": meta["label"],
            "scale": {
                "min": meta["min"],
                "max": meta["max"],
                "unit": meta["unit"],
                "description": meta["scale"],
            },
            "completed_rounds": completed,
            "rounds_with_results": with_results,
            "rounds_with_valid_scores": len(scored),
            "candidates": len({e["student_id"] for e in scored}),
            "avg_score": round(sum(scores) / len(scores), 2) if scores else None,
            "min_score": round(min(scores), 2) if scores else None,
            "max_score": round(max(scores), 2) if scores else None,
            "available": bool(scores),
            "definition": _TYPE_DEFINITION[ctype],
        }
        if not completed:
            block["reason"] = (
                f"No completed {meta['label'].lower()} round in the selected period "
                "and drive scope."
            )
        elif not with_results:
            block["reason"] = (
                f"{completed} completed {meta['label'].lower()} round(s) in scope, but "
                "none carries a persisted result, so no score is available."
            )
        elif not scored:
            block["reason"] = (
                f"{with_results} completed {meta['label'].lower()} round(s) have a "
                "persisted result, but none is usable scored evidence — results are "
                "excluded, never counted as zero."
            )
        else:
            block["reason"] = None
        return block

    assessment_components = {t: _assessment_component(t) for t in _ASSESSMENT_TYPES}
    total_completed_rounds = sum(assessment_components[t]["completed_rounds"] for t in _ASSESSMENT_TYPES)
    total_scored_results = sum(assessment_components[t]["rounds_with_valid_scores"] for t in _ASSESSMENT_TYPES)
    candidates_with_completed_rounds = len({
        r["student_id"] for t in _ASSESSMENT_TYPES for r in rounds_by_type[t]
    })
    candidates_assessed = len({
        r["student_id"] for t in _ASSESSMENT_TYPES for r in scored_by_type[t]
    })

    if candidates_with_completed_rounds:
        candidates_assessed_block = {
            "available": True,
            "value": candidates_assessed,
            "denominator": candidates_with_completed_rounds,
            "definition": (
                "Distinct candidates with at least one usable scored result (graded "
                "aptitude responses, a countable coding submission, or a scored "
                "interview turn) out of distinct candidates with at least one "
                "completed assessment round in scope. A completed round without a "
                "persisted result does not make its candidate 'assessed'."
            ),
            "reason": None,
        }
        if candidates_assessed == 0:
            candidates_assessed_block["reason"] = (
                f"{candidates_with_completed_rounds} candidate(s) completed an "
                "assessment round in scope, but none has a usable scored result."
            )
    else:
        candidates_assessed_block = {
            "available": False,
            "value": None,
            "denominator": 0,
            "definition": (
                "Distinct candidates with at least one usable scored result out of "
                "distinct candidates with at least one completed assessment round "
                "in scope."
            ),
            "reason": (
                "No candidate completed an assessment round in the selected period "
                "and drive scope."
            ),
        }

    # Primary type = the type with the most usable scored results (ties keep
    # the fixed aptitude > coding > interview order). The card states which
    # type and scale it reports; every type is also shown separately.
    _primary_type = None
    if total_scored_results:
        _primary_type = max(
            _ASSESSMENT_TYPES,
            key=lambda t: (
                assessment_components[t]["rounds_with_valid_scores"],
                -_ASSESSMENT_TYPES.index(t),
            ),
        )
    if _primary_type and assessment_components[_primary_type]["rounds_with_valid_scores"]:
        _meta = _TYPE_META[_primary_type]
        _scores = [e["score"] for e in scored_by_type[_primary_type]]
        average_assessed_performance = {
            "available": True,
            "value": round(sum(_scores) / len(_scores), 2),
            "attempts": len(_scores),
            "candidates": len({e["student_id"] for e in scored_by_type[_primary_type]}),
            "assessment_type": _primary_type,
            "assessment_label": _meta["label"],
            "scale": {
                "min": _meta["min"],
                "max": _meta["max"],
                "unit": _meta["unit"],
                "description": _meta["scale"],
            },
            "types_included": [_primary_type],
            "types_excluded": [
                {
                    "type": t,
                    "assessment_label": _TYPE_META[t]["label"],
                    "completed_rounds": assessment_components[t]["completed_rounds"],
                    "rounds_with_valid_scores": assessment_components[t][
                        "rounds_with_valid_scores"
                    ],
                    "reason": (
                        "No usable scored result for this type in scope."
                        if not assessment_components[t]["rounds_with_valid_scores"]
                        else "Reported separately in components; scales are not mixed."
                    ),
                }
                for t in _ASSESSMENT_TYPES
                if t != _primary_type
            ],
            "definition": (
                "Mean of each usable scored round result for the assessment type with "
                "the most scored rounds in scope. Scales are never mixed: only one "
                "type and its own 0-100 / 0-1 scale contribute to this average, and "
                "completed rounds without a persisted result are excluded rather than "
                "counted as zero."
            ),
            "reason": None,
        }
    else:
        average_assessed_performance = {
            "available": False,
            "value": None,
            "attempts": 0,
            "candidates": 0,
            "assessment_type": None,
            "assessment_label": None,
            "scale": None,
            "types_included": [],
            "types_excluded": [
                {
                    "type": t,
                    "assessment_label": _TYPE_META[t]["label"],
                    "completed_rounds": assessment_components[t]["completed_rounds"],
                    "rounds_with_valid_scores": assessment_components[t][
                        "rounds_with_valid_scores"
                    ],
                    "reason": (
                        "No usable scored result for this type in scope."
                        if not assessment_components[t]["rounds_with_valid_scores"]
                        else "Reported separately in components; scales are not mixed."
                    ),
                }
                for t in _ASSESSMENT_TYPES
            ],
            "definition": (
                "Mean of each usable scored round result for the assessment type with "
                "the most scored rounds in scope. Scales are never mixed."
            ),
            "reason": (
                "No assessment type has a usable scored result in scope — completed "
                "rounds without graded aptitude responses, a countable coding "
                "submission, or a scored interview turn are excluded, never zeroed."
            ),
        }

    # Improvement: earliest -> latest per candidate, within a single type only.
    improvement_by_type: dict[str, dict] = {}
    for _t in _ASSESSMENT_TYPES:
        _by_student: dict[int, list] = defaultdict(list)
        for _e in scored_by_type[_t]:
            _by_student[_e["student_id"]].append(_e)
        _deltas: list[float] = []
        for _rows in _by_student.values():
            if len(_rows) < 2:
                continue
            _ordered = sorted(_rows, key=lambda x: (x["at"] or datetime.min, x["round_id"]))
            _deltas.append(round(_ordered[-1]["score"] - _ordered[0]["score"], 2))
        if _deltas:
            _sorted_deltas = sorted(_deltas)
            _n = len(_sorted_deltas)
            _mid = _n // 2
            improvement_by_type[_t] = {
                "candidates_compared": _n,
                "improved": sum(1 for d in _deltas if d > 0),
                "unchanged": sum(1 for d in _deltas if d == 0),
                "declined": sum(1 for d in _deltas if d < 0),
                "mean_delta": round(sum(_sorted_deltas) / _n, 2),
                "median_delta": (
                    _sorted_deltas[_mid] if _n % 2
                    else round((_sorted_deltas[_mid - 1] + _sorted_deltas[_mid]) / 2, 2)
                ),
                "scale": {
                    "min": _TYPE_META[_t]["min"],
                    "max": _TYPE_META[_t]["max"],
                    "unit": _TYPE_META[_t]["unit"],
                    "description": _TYPE_META[_t]["scale"],
                },
            }

    if improvement_by_type:
        _pick = max(
            _ASSESSMENT_TYPES,
            key=lambda t: (
                improvement_by_type.get(t, {}).get("candidates_compared", 0),
                -_ASSESSMENT_TYPES.index(t),
            ),
        )
        _imp = improvement_by_type[_pick]
        improving_candidates = {
            "available": True,
            "value": _imp["improved"],
            "denominator": _imp["candidates_compared"],
            "assessment_type": _pick,
            "assessment_label": _TYPE_META[_pick]["label"],
            "improved": _imp["improved"],
            "unchanged": _imp["unchanged"],
            "declined": _imp["declined"],
            "mean_delta": _imp["mean_delta"],
            "median_delta": _imp["median_delta"],
            "scale": _imp["scale"],
            "by_type": {
                t: improvement_by_type[t]
                for t in _ASSESSMENT_TYPES
                if t in improvement_by_type
            },
            "definition": (
                "Distinct candidates with at least two scored rounds of one "
                "assessment type: latest round result minus earliest round result on "
                "that type's own scale (ties in type selection keep the fixed "
                "aptitude > coding > interview order). Numerator is candidates whose "
                "delta is greater than zero; denominator is candidates compared. "
                "Descriptive only — repeat attempts are not claimed as the cause."
            ),
            "reason": None,
        }
    else:
        improving_candidates = {
            "available": False,
            "value": None,
            "denominator": 0,
            "assessment_type": None,
            "assessment_label": None,
            "improved": 0,
            "unchanged": 0,
            "declined": 0,
            "mean_delta": None,
            "median_delta": None,
            "scale": None,
            "by_type": {},
            "definition": (
                "Distinct candidates with at least two scored rounds of one "
                "assessment type: latest round result minus earliest round result on "
                "that type's own scale."
            ),
            "reason": (
                "No assessment type has a candidate with two or more scored rounds "
                "in the selected period and drive scope."
            ),
        }

    coverage_by_type = []
    for _t in _ASSESSMENT_TYPES:
        _comp = assessment_components[_t]
        coverage_by_type.append({
            "type": _t,
            "label": _comp["label"],
            "completed_rounds": _comp["completed_rounds"],
            "rounds_with_results": _comp["rounds_with_results"],
            "rounds_with_valid_scores": _comp["rounds_with_valid_scores"],
            "coverage_pct": (
                round(
                    _comp["rounds_with_valid_scores"]
                    / _comp["completed_rounds"] * 100,
                    1,
                )
                if _comp["completed_rounds"] else None
            ),
        })
    if total_completed_rounds:
        evidence_coverage = {
            "available": True,
            "value": round(total_scored_results / total_completed_rounds * 100, 1),
            "numerator": total_scored_results,
            "denominator": total_completed_rounds,
            "by_type": coverage_by_type,
            "definition": (
                "Completed assessment rounds with a usable scored result divided by "
                "all completed assessment rounds in scope, summed across aptitude, "
                "coding and interview (each type's own evidence rule, per "
                "assessment_performance.components). Unscored completed rounds lower "
                "coverage; they are never counted as scored zeros."
            ),
            "reason": None,
        }
    else:
        evidence_coverage = {
            "available": False,
            "value": None,
            "numerator": 0,
            "denominator": 0,
            "by_type": coverage_by_type,
            "definition": (
                "Completed assessment rounds with a usable scored result divided by "
                "all completed assessment rounds in scope."
            ),
            "reason": (
                "No completed assessment round in the selected period and drive scope."
            ),
        }

    # Preparation progress: trend of the primary type's scored round results.
    progress_points: list[dict] = []
    progress_granularity = None
    progress_type = None
    if _primary_type:
        progress_type = _primary_type
        _dated = [
            e for e in scored_by_type[_primary_type]
            if e["at"] is not None
        ]
        if _dated:
            _span_days = (
                max(e["at"] for e in _dated) - min(e["at"] for e in _dated)
            ).days + 1
            progress_granularity = "weekly" if _span_days <= 120 else "monthly"
            _buckets: dict[str, dict] = defaultdict(
                lambda: {"scores": [], "students": set()}
            )
            for _e in _dated:
                _d = _e["at"].date()
                if progress_granularity == "weekly":
                    _d = _d - timedelta(days=_d.weekday())
                    _key = _d.isoformat()
                else:
                    _key = f"{_d.year}-{_d.month:02d}"
                _buckets[_key]["scores"].append(_e["score"])
                _buckets[_key]["students"].add(_e["student_id"])
            progress_points = [
                {
                    "bucket_start": _k,
                    "avg_score": round(sum(v["scores"]) / len(v["scores"]), 2),
                    "attempts": len(v["scores"]),
                    "candidates": len(v["students"]),
                }
                for _k, v in sorted(_buckets.items())
            ]

    # Aptitude topic performance: pooled graded responses per topic.
    topic_rows: list[dict] = []
    if apt_round_ids:
        topic_rows = [
            {
                "topic": _name or "Untagged",
                "responses": int(_resp or 0),
                "correct": int(_corr or 0),
                "accuracy": round(int(_corr or 0) / int(_resp or 0) * 100, 1)
                if _resp else 0.0,
                "candidates": int(_cands or 0),
            }
            for _name, _resp, _corr, _cands in (
                db.query(
                    AptitudeTopic.name,
                    func.count(AptitudeAttempt.id),
                    func.sum(case((AptitudeAttempt.is_correct.is_(True), 1), else_=0)),
                    func.count(func.distinct(AssessmentSession.user_id)),
                )
                .select_from(AptitudeAttempt)
                .join(AssessmentRound, AptitudeAttempt.round_id == AssessmentRound.id)
                .join(AssessmentSession, AssessmentRound.session_id == AssessmentSession.id)
                .outerjoin(AptitudeQuestion, AptitudeAttempt.question_id == AptitudeQuestion.id)
                .outerjoin(AptitudeTopic, AptitudeQuestion.topic_id == AptitudeTopic.id)
                .filter(
                    AptitudeAttempt.round_id.in_(apt_round_ids),
                    AptitudeAttempt.is_correct.isnot(None),
                )
                .group_by(AptitudeTopic.name)
                .order_by(func.count(AptitudeAttempt.id).desc())
                .all()
            )
            if _resp
        ]

    assessment_performance = {
        "available": total_scored_results > 0,
        "note": (
            "Assessment performance is computed only from persisted, scored evidence "
            "in the selected period and drive scope. Completed rounds without graded "
            "aptitude responses, a countable coding submission, or a scored interview "
            "turn have no result and are excluded from averages and coverage "
            "numerators — never counted as a zero. Participation, completion, raw "
            "answer counts and transcript length are never used as a performance "
            "substitute, and the three assessment scales are never averaged together."
        ),
        "summary": {
            "candidates_assessed": candidates_assessed_block,
            "average_assessed_performance": average_assessed_performance,
            "improving_candidates": improving_candidates,
            "evidence_coverage": evidence_coverage,
        },
        "components": {
            t: assessment_components[t] for t in _ASSESSMENT_TYPES
        },
        "progress": {
            "available": bool(progress_points),
            "assessment_type": progress_type,
            "granularity": progress_granularity,
            "scale": (
                {
                    "min": _TYPE_META[progress_type]["min"],
                    "max": _TYPE_META[progress_type]["max"],
                    "unit": _TYPE_META[progress_type]["unit"],
                    "description": _TYPE_META[progress_type]["scale"],
                }
                if progress_type else None
            ),
            "note": (
                "Usable scored round results for the assessment type with the most "
                "scored rounds, bucketed weekly when the observed span is at most 120 "
                "days and monthly otherwise. Only buckets with at least one observed "
                "result are returned — missing periods are never interpolated."
                if progress_points else
                "No usable scored result with a completion timestamp exists for any "
                "assessment type in scope, so no trend is drawn."
            ),
            "points": progress_points,
        },
        "topic_performance": {
            "available": bool(topic_rows),
            "assessment_type": "aptitude",
            "note": (
                "Aptitude topic accuracy pools graded responses (correct / graded x "
                "100) across in-scope completed aptitude rounds; it is an assessment "
                "result, not a competency-readiness or skill-gap score — no "
                "competency mapping is involved. Topics with no graded response are "
                "omitted."
            ),
            "rows": topic_rows,
            "definition": (
                "Per topic: responses = graded aptitude responses (is_correct "
                "recorded), correct = responses answered correctly, accuracy = "
                "correct / responses x 100, candidates = distinct candidates with at "
                "least one graded response. Rounds without graded responses "
                "contribute nothing."
            ),
        },
        "definitions": {
            "completed_round": (
                "An assessment round with status='completed' on an in-scope mock-drive "
                "assessment session, filtered to the reporting period by the round's "
                "completion time (falling back to its session or context event time)."
            ),
            "rounds_with_results": (
                "Completed rounds that carry a persisted result: at least one graded "
                "aptitude response, at least one coding submission, or at least one "
                "interview turn. A completed round without one is not evidence."
            ),
            "rounds_with_valid_scores": (
                "Completed rounds whose result is usable scored evidence under this "
                "endpoint's per-type rules (see components). This is the coverage "
                "numerator; it is always less than or equal to rounds_with_results."
            ),
            "candidates_assessed": (
                "Distinct candidates with at least one round_with_valid_score in "
                "scope, over distinct candidates with at least one completed round."
            ),
            "scale_separation": (
                "Aptitude accuracy is a 0-100 percentage; coding and interview "
                "results are 0-1 scores. They are reported per type and never "
                "pooled, ranked against each other, or averaged together."
            ),
        },
    }

    # ── KPI: average readiness ──────────────────────────────────────────
    scores = [a["score"] for a in attempts]
    unique_scored = {a["student_id"] for a in attempts}
    final_attempts = sum(1 for a in attempts if a["score_status"] == "final")
    provisional_attempts = sum(1 for a in attempts if a["score_status"] == "provisional")

    if scores:
        average_readiness = {
            "available": True,
            "value": round(sum(scores) / len(scores), 2),
            "eligible_candidates": len(unique_scored),
            "attempts": len(scores),
            "final_attempts": final_attempts,
            "provisional_attempts": provisional_attempts,
            "definition": _READINESS_SCORE_DEFINITION,
        }
    else:
        if completed_contexts == 0:
            _no_score_reason = (
                "No completed mock-drive attempt in the selected period and drive "
                "scope, so no competency readiness score can be computed."
            )
        elif contexts_with_snapshot == 0:
            _no_score_reason = (
                f"{completed_contexts} completed mock-drive attempt(s) in scope, but "
                "none carries a pinned blueprint snapshot, so no competency readiness "
                "score can be computed."
            )
        elif contexts_with_configured_competencies == 0:
            _no_score_reason = (
                f"{contexts_with_snapshot} of {completed_contexts} completed attempt(s) "
                "carry a pinned blueprint snapshot, but 0 of them configure any "
                "competency, so no readiness score exists (missing configured "
                "competencies)."
            )
        elif contexts_with_evidence_mappings == 0:
            _no_score_reason = (
                f"{contexts_with_configured_competencies} completed attempt(s) configure "
                "competencies, but 0 session has mapped competency evidence, so no "
                "readiness score exists (missing evidence mappings)."
            )
        else:
            _no_score_reason = (
                "No completed mock-drive attempt has a computable competency readiness "
                "score (pinned blueprint competency scoring exists but produced no "
                "usable scored evidence)."
            )
        average_readiness = {
            "available": False,
            "value": None,
            "eligible_candidates": 0,
            "attempts": 0,
            "final_attempts": 0,
            "provisional_attempts": 0,
            "definition": _READINESS_SCORE_DEFINITION,
            "reason": _no_score_reason,
        }

    # ── KPI: improvement across multiple attempts ───────────────────────
    by_student: dict[int, list] = defaultdict(list)
    for a in attempts:
        by_student[a["student_id"]].append(a)

    deltas: list[float] = []
    improved = unchanged = declined = 0
    for rows in by_student.values():
        if len(rows) < 2:
            continue
        ordered = sorted(rows, key=lambda r: (r["at"] or datetime.min))
        delta = ordered[-1]["score"] - ordered[0]["score"]
        deltas.append(round(delta, 2))
        if delta > 0:
            improved += 1
        elif delta < 0:
            declined += 1
        else:
            unchanged += 1

    if deltas:
        sorted_deltas = sorted(deltas)
        n = len(sorted_deltas)
        mid = n // 2
        median_delta = (
            sorted_deltas[mid] if n % 2
            else round((sorted_deltas[mid - 1] + sorted_deltas[mid]) / 2, 2)
        )
        attempt_improvement = {
            "available": True,
            "students_compared": n,
            "mean_delta": round(sum(sorted_deltas) / n, 2),
            "median_delta": median_delta,
            "improved": improved,
            "unchanged": unchanged,
            "declined": declined,
            "definition": _ATTEMPT_IMPROVEMENT_DEFINITION,
        }
    else:
        attempt_improvement = {
            "available": False,
            "students_compared": 0,
            "mean_delta": None,
            "median_delta": None,
            "improved": 0,
            "unchanged": 0,
            "declined": 0,
            "definition": _ATTEMPT_IMPROVEMENT_DEFINITION,
            "reason": (
                "Fewer than two eligible scored attempts exist for any single candidate."
            ),
        }

    # ── KPIs EDI5 cannot support — honest unavailable, never invented ────
    threshold_percentage = {
        "available": False,
        "value": None,
        "eligible_candidates": 0,
        "denominator": 0,
        "reason": (
            "EDI5 defines no authoritative institutional readiness threshold. The 75/65 "
            "score bands in the candidate-facing report are display-only strength/focus "
            "markers, not a readiness standard; a product decision is required before "
            "this metric can be shown."
        ),
    }
    placement_rate = {
        "available": False,
        "value": None,
        "placed_candidates": 0,
        "denominator": 0,
        "reason": (
            "EDI5 persists no placement or offer records for mock drives, so no "
            "authoritative numerator or denominator exists."
        ),
    }

    # ── Readiness over time (ISO-week buckets of eligible attempts) ─────
    week_map: dict[str, dict] = defaultdict(lambda: {"scores": [], "students": set()})
    for a in attempts:
        when = a["at"]
        if when is None:
            continue
        monday = (when.date() - timedelta(days=when.weekday())).isoformat()
        week_map[monday]["scores"].append(a["score"])
        week_map[monday]["students"].add(a["student_id"])
    readiness_over_time = [
        {
            "bucket_start": key,
            "avg_readiness": round(sum(v["scores"]) / len(v["scores"]), 2),
            "attempts": len(v["scores"]),
            "candidates": len(v["students"]),
        }
        for key, v in sorted(week_map.items())
    ]

    # ── Distribution (equal-width numeric buckets on the 0-100 scale) ───
    bucket_edges = [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100)]
    dist_total = len(scores)
    dist_buckets = []
    for i, (lo, hi) in enumerate(bucket_edges):
        if i < len(bucket_edges) - 1:
            count = sum(1 for s in scores if lo <= s < hi)
        else:
            count = sum(1 for s in scores if lo <= s <= hi)
        dist_buckets.append({
            "label": f"{lo}\u2013{hi}",
            "min": lo,
            "max": hi,
            "count": count,
            "pct": round(count / dist_total * 100, 1) if dist_total else 0.0,
        })
    readiness_distribution = {
        "total": dist_total,
        "note": (
            "Equal-width numeric buckets on the 0-100 score scale. These are "
            "distribution buckets, not readiness categories or thresholds."
        ),
        "buckets": dist_buckets,
    }

    # ── By department (real names from student profiles) ────────────────
    # One grouped read for every scored candidate (no per-student N+1).
    _scored_ids = sorted({a["student_id"] for a in attempts})
    if _scored_ids:
        for _prof in (
            db.query(StudentProfile)
            .filter(StudentProfile.user_id.in_(_scored_ids))
            .all()
        ):
            dept_cache[_prof.user_id] = _prof.department or "Unspecified"
    for _sid in _scored_ids:
        dept_cache.setdefault(_sid, "Unspecified")

    dept_map: dict[str, dict] = defaultdict(lambda: {"scores": [], "students": set()})
    for a in attempts:
        dept = _department_of(a["student_id"])
        dept_map[dept]["scores"].append(a["score"])
        dept_map[dept]["students"].add(a["student_id"])
    by_department = [
        {
            "department": dept,
            "candidates": len(v["students"]),
            "attempts": len(v["scores"]),
            "avg_readiness": round(sum(v["scores"]) / len(v["scores"]), 2),
        }
        for dept, v in sorted(dept_map.items())
    ]

    # ── Skill gaps (configured snapshot competencies only) ──────────────
    def _skill_gap_view(source_type: str | None = None) -> dict:
        gap_index: dict[str, dict] = {}
        eligible_attempt_count = 0
        for attempt in skill_gap_attempts:
            if source_type and source_type not in attempt["assessment_types"]:
                continue
            eligible_attempt_count += 1
            for comp in attempt["competencies"]:
                cid = comp["competency_id"]
                gi = gap_index.setdefault(cid, {
                    "name": comp["competency_name"], "scores": [], "evidence": 0,
                    "assessed": 0, "eligible": 0, "candidate_ids": set(), "sources": set(),
                    "expected_sources": set(),
                })
                gi["eligible"] += 1
                gi["expected_sources"].update(
                    [source_type] if source_type else attempt["assessment_types"]
                )
                if attempt["student_id"] is not None:
                    gi["candidate_ids"].add(attempt["student_id"])
                score = comp.get("normalized_score") if source_type is None else (
                    comp.get("assessment_type_scores", {}).get(source_type)
                )
                evidence = comp.get("evidence_count", 0) if source_type is None else (
                    comp.get("assessment_type_evidence_counts", {}).get(source_type, 0)
                )
                gi["evidence"] += evidence or 0
                if score is not None:
                    gi["scores"].append(score)
                    gi["assessed"] += 1
                    gi["sources"].update(comp.get("sources", [])) if source_type is None else gi["sources"].add(source_type)

        assessed_rows, unassessed_rows = [], []
        for cid, gi in gap_index.items():
            row = {
                "competency_id": str(cid), "competency_name": gi["name"],
                "candidates": gi["eligible"], "unique_candidates": len(gi["candidate_ids"]),
                "assessed": gi["assessed"], "evidence_count": gi["evidence"],
                "assessment_types": sorted(gi["sources"]),
                "expected_assessment_types": sorted(gi["expected_sources"]),
                "coverage_rate": round(gi["assessed"] / gi["eligible"] * 100, 1)
                if gi["eligible"] else 0.0,
            }
            if gi["scores"]:
                row["avg_score"] = round(sum(gi["scores"]) / len(gi["scores"]), 2)
                row["gap_to_100"] = round(100.0 - row["avg_score"], 2)
                assessed_rows.append(row)
            else:
                row["avg_score"] = row["gap_to_100"] = None
                unassessed_rows.append(row)
        for row in assessed_rows + unassessed_rows:
            row["assessed_attempts"] = row["assessed"]
            row["eligible_attempts"] = row["candidates"]
            row["evidence_items"] = row["evidence_count"]
            row["coverage_percent"] = row["coverage_rate"]
            row["evidence_sources"] = row["assessment_types"]
        assessed_rows.sort(
            key=lambda item: (-item["gap_to_100"], item["competency_name"] or "")
        )
        unassessed_rows.sort(key=lambda item: item["competency_name"] or "")
        scores = [row["avg_score"] for row in assessed_rows]
        summary = {
            "competencies_assessed": len(assessed_rows),
            "competencies_unassessed": len(unassessed_rows),
            "configured_competencies": len(assessed_rows) + len(unassessed_rows),
            "eligible_attempts": eligible_attempt_count,
            "configuration_known": eligible_attempt_count > 0,
            "average_competency_score": round(sum(scores) / len(scores), 2) if scores else None,
            "largest_competency_gap": max((row["gap_to_100"] for row in assessed_rows), default=None),
        }
        return {
            "available": bool(assessed_rows), "competencies": assessed_rows,
            "unassessed": unassessed_rows, "summary": summary,
        }

    supported_skill_gap_types = sorted({
        assessment_type for attempt in skill_gap_attempts
        for assessment_type in attempt["assessment_types"]
    })
    skill_gaps = {
        **_skill_gap_view(),
        "assessment_types": supported_skill_gap_types,
        "by_assessment_type": {
            assessment_type: _skill_gap_view(assessment_type)
            for assessment_type in supported_skill_gap_types
        },
        "definition": (
            "Gap = 100 - average normalized competency score. Coverage is assessed "
            "attempts over completed configured attempts where that source is enabled. "
            "Scores use countable evidence explicitly mapped to the pinned blueprint. "
            "Aptitude and coding are supported; unmapped interview results are excluded."
        ),
    }

    # ── Deterministic insights from verified aggregates only ────────────
    # Readiness Intelligence: deterministic summaries of verified aggregates.
    insights = []
    eligible_attempts = completed_contexts
    scored_students = len(unique_scored)
    if scores:
        mean_readiness = round(sum(scores) / len(scores), 2)
        insights.append({
            "id": "overall-readiness",
            "category": "overall",
            "title": "Overall scored readiness",
            "summary": (
                f"Mean readiness is {mean_readiness}/100 across {len(scores)} scored "
                f"completed attempts from {scored_students} distinct students."
            ),
            "evidence": (
                f"{len(scores)} scored completed attempts from {scored_students} distinct "
                f"students; {eligible_attempts} completed attempts were eligible. "
                "Students without a computable score are excluded, not scored as zero."
            ),
            "sample_size": scored_students,
            "denominator": eligible_attempts,
            "metric": "mean competency readiness score (0-100) across scored attempts",
            "period": period,
            "action": None,
        })

    # A population pattern requires multiple students for each competency and at
    # least two comparable competencies. The mean is descriptive, not a threshold.
    repeated_competencies = [
        row for row in skill_gaps["competencies"] if row.get("unique_candidates", 0) >= 2
    ]
    if len(repeated_competencies) >= 2 and scores:
        population_mean = sum(scores) / len(scores)
        development = [r for r in repeated_competencies if r["avg_score"] < population_mean]
        strengths = [r for r in repeated_competencies if r["avg_score"] >= population_mean]
        parts = []
        if strengths:
            parts.append("Relative strengths: " + ", ".join(
                f"{r['competency_name']} ({r['avg_score']}/100; {r['unique_candidates']} students)"
                for r in strengths
            ))
        if development:
            parts.append("Below-average competencies: " + ", ".join(
                f"{r['competency_name']} ({r['avg_score']}/100; {r['unique_candidates']} students)"
                for r in development
            ))
        if parts:
            insights.append({
                "id": "competency-patterns",
                "category": "competency",
                "title": "Competency strengths and development patterns",
                "summary": ". ".join(parts) + ".",
                "evidence": (
                    "Uses normalized scores from eligible completed attempts and includes "
                    "competencies assessed for at least two distinct students. Below-average "
                    "is descriptive relative to the scored-attempt mean, not a pass threshold."
                ),
                "sample_size": len(repeated_competencies),
                "denominator": len(skill_gaps["competencies"]),
                "metric": "normalized competency scores compared with the mean readiness score (0-100)",
                "period": period,
                "action": ({"label": "Review competency evidence", "route": "/tpo/analytics"}
                           if development else None),
            })

    # Department comparisons share the same scoring policy and filters. Two
    # students is the minimum for a group pattern; differences remain descriptive.
    department_student_scores: dict[str, dict[int, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for attempt in attempts:
        department_student_scores[_department_of(attempt["student_id"])][
            attempt["student_id"]
        ].append(attempt["score"])
    comparable_departments = []
    for department, student_scores in department_student_scores.items():
        if len(student_scores) < 2:
            continue
        per_student_means = [sum(values) / len(values) for values in student_scores.values()]
        comparable_departments.append({
            "department": department,
            "candidates": len(student_scores),
            "avg_readiness": round(sum(per_student_means) / len(per_student_means), 2),
        })
    if len(comparable_departments) >= 2:
        low = min(comparable_departments, key=lambda r: (r["avg_readiness"], r["department"]))
        high = max(comparable_departments, key=lambda r: (r["avg_readiness"], r["department"]))
        if low["department"] != high["department"]:
            insights.append({
                "id": "department-readiness-pattern",
                "category": "cohort",
                "title": "Observed readiness variation across departments",
                "summary": (
                    f"{low['department']} averages {low['avg_readiness']}/100 "
                    f"({low['candidates']} students); {high['department']} averages "
                    f"{high['avg_readiness']}/100 ({high['candidates']} students)."
                ),
                "evidence": (
                    "Both groups use the same readiness scoring policy and include at least "
                    "two distinct students. This is descriptive, not a ranking or a claim "
                    "of statistical significance."
                ),
                "sample_size": low["candidates"] + high["candidates"],
                "denominator": scored_students,
                "metric": "mean of each student's mean readiness score (0-100) by department",
                "period": period,
                "action": {"label": "Review department analytics", "route": "/tpo/analytics"},
            })

    if eligible_attempts:
        missing_attempts = max(0, eligible_attempts - len(scores))
        coverage_pct = round(len(scores) / eligible_attempts * 100, 1)
        insights.append({
            "id": "evidence-reliability",
            "category": "evidence",
            "title": "Assessment evidence coverage",
            "summary": (
                f"A computable readiness score is available for {len(scores)} of "
                f"{eligible_attempts} completed attempts ({coverage_pct}%). "
                f"{missing_attempts} completed attempts lack a score; missing evidence "
                "is not interpreted as low readiness."
            ),
            "evidence": (
                f"{len(scores)} scored attempts / {eligible_attempts} completed attempts. "
                "Scoring requires a pinned blueprint, configured competencies, and "
                "countable mapped assessment evidence."
            ),
            "sample_size": len(scores),
            "denominator": eligible_attempts,
            "metric": "scored completed attempts / all completed attempts",
            "period": period,
            "action": ({"label": "Review evidence coverage", "route": "/tpo/analytics"}
                       if missing_attempts else None),
        })

    # Derived from mock_drives + assessment_contexts. Nothing here is a
    # readiness, competency, or placement value, and no score is substituted
    # for a count.
    status_q = db.query(_MD.status, func.count(_MD.id))
    if company:
        status_q = status_q.filter(_MD.company_name == company)
    if role:
        status_q = status_q.filter(_MD.target_role == role)
    if drive_status:
        status_q = status_q.filter(_MD.status == drive_status)
    status_counts = dict(status_q.group_by(_MD.status).all())

    status_total = int(sum(status_counts.values()))
    status_rows = [
        {
            "status": s,
            "drives": int(status_counts.get(s, 0)),
            "pct": (
                round(status_counts.get(s, 0) / status_total * 100, 1)
                if status_total else 0.0
            ),
            "analysed": s in ("published", "active", "completed"),
        }
        for s in MOCK_DRIVE_STATUSES
        if status_counts.get(s, 0)
    ]

    g_enrolled = len(participant_statuses)
    g_completed = sum(
        1 for st in participant_statuses.values() if "completed" in st
    )
    g_in_progress = sum(
        1 for st in participant_statuses.values()
        if "completed" not in st and "active" in st
    )
    g_not_started = g_enrolled - g_completed - g_in_progress

    # Participation over time — bucketed by the timestamp of each event.
    _event_dates = []
    for _c in scoped_contexts:
        if _c.created_at is not None:
            _event_dates.append(_c.created_at.date())
        if _c.completed_at is not None:
            _event_dates.append(_c.completed_at.date())
    _span_days = (
        (max(_event_dates) - min(_event_dates)).days + 1 if _event_dates else 0
    )
    granularity = "daily" if _span_days <= 45 else "weekly"

    def _bucket_key(dt):
        _d = dt.date()
        if granularity == "weekly":
            _d = _d - timedelta(days=_d.weekday())
        return _d.isoformat()

    reg_map: dict[str, int] = defaultdict(int)
    comp_map: dict[str, int] = defaultdict(int)
    for _c in scoped_contexts:
        if _c.created_at is not None:
            reg_map[_bucket_key(_c.created_at)] += 1
        if _c.completed_at is not None:
            comp_map[_bucket_key(_c.completed_at)] += 1
    activity_over_time = [
        {
            "bucket_start": _k,
            "registrations": reg_map.get(_k, 0),
            "completions": comp_map.get(_k, 0),
        }
        for _k in sorted(set(reg_map) | set(comp_map))
    ]

    drive_activity = {
        "available": status_total > 0,
        "note": (
            "Drive activity analytics come from mock-drive and assessment-context "
            "records only. They describe participation and completion, never "
            "readiness, competency, or placement outcomes."
        ),
        "definitions": {
            "eligible_participant": (
                "A distinct student with at least one assessment context linked to "
                "an in-scope mock drive (purpose='mock_drive') created inside the "
                "reporting period. Repeated attempts by the same student count once."
            ),
            "completed_participant": (
                "An eligible participant with at least one context whose "
                "authoritative context.status is 'completed'."
            ),
            "in_progress_participant": (
                "An eligible participant with no completed context and at least one "
                "context with status 'active'."
            ),
            "not_started_participant": (
                "An eligible participant with neither a completed nor an active "
                "context. The three categories are mutually exclusive and sum to "
                "eligible_participant."
            ),
            "completion_rate": (
                "completed_participants / eligible_participants x 100, rounded to "
                "one decimal. Unavailable (null) when the denominator is 0 — never "
                "rendered as a fabricated 0%."
            ),
            "event_timestamps": (
                "Registrations use assessment_contexts.created_at and completions "
                "use assessment_contexts.completed_at."
            ),
        },
        "status_distribution": {
            "note": (
                "Counts of drives by the authoritative mock_drives.status column, "
                "for every drive matching the company/role/status filters. Draft "
                "drives are listed here for completeness but are excluded from "
                "every other metric on this page (existing endpoint policy: only "
                "published/active/completed drives are analysed). The "
                "reporting-period filter applies to attempt events, not to the "
                "drive inventory — matching the behaviour of by_drive."
            ),
            "total": status_total,
            "analysed": int(sum(r["drives"] for r in status_rows if r["analysed"])),
            "excluded": int(sum(r["drives"] for r in status_rows if not r["analysed"])),
            "rows": status_rows,
        },
        "kpis": {
            "drives_in_scope": len(drives),
            "participants_enrolled": g_enrolled,
            "participants_completed": g_completed,
            "participants_in_progress": g_in_progress,
            "participants_not_started": g_not_started,
            "completion_rate": (
                round(g_completed / g_enrolled * 100, 1) if g_enrolled else None
            ),
            "contexts": len(scoped_contexts),
            "completed_contexts": completed_contexts,
        },
        "by_drive": activity_rows,
        "over_time": {
            "granularity": granularity,
            "note": (
                "Real event timestamps persisted on assessment contexts: "
                "registrations (created_at) and completions (completed_at), "
                f"bucketed {granularity} over the reporting period. Only buckets "
                "with at least one observed event are returned — missing periods "
                "are never interpolated, and a drive's current status is never "
                "converted into a historical event."
            ),
            "points": activity_over_time,
        },
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "filters_applied": {
            "period": period,
            "company": company,
            "role": role,
            "drive_status": drive_status,
        },
        "score_scale": {
            "min": 0,
            "max": 100,
            "definition": _READINESS_SCORE_DEFINITION,
            "scoring_policy_versions": [SCORING_POLICY_VERSION],
        },
        "coverage": {
            "drives_examined": len(drives),
            "contexts_examined": contexts_examined,
            "students_with_contexts": len(students_with_contexts),
            "completed_contexts": completed_contexts,
            "contexts_with_snapshot": contexts_with_snapshot,
            "contexts_with_configured_competencies": contexts_with_configured_competencies,
            "contexts_with_evidence_mappings": contexts_with_evidence_mappings,
            "scored_attempts": len(scores),
            "unique_scored_candidates": len(unique_scored),
            "skipped_scoring_errors": skipped_scoring_errors,
            # Follow-up metrics (Section 2). Distinct candidates who completed
            # assessment activity but have no usable scored attempt, and the
            # count of completed attempts needing scoring follow-up.
            "candidates_with_completed_no_usable_score": len(
                students_with_completed_contexts - unique_scored
            ) if completed_contexts else 0,
            "rounds_needing_followup": (
                followup_missing_snapshot + followup_no_competencies
                + followup_no_mappings + followup_no_usable_score
                + followup_scoring_error
            ),
            "followup_breakdown": {
                "completed_attempts_needing_followup": (
                    followup_missing_snapshot + followup_no_competencies
                    + followup_no_mappings + followup_no_usable_score
                    + followup_scoring_error
                ),
                "missing_pinned_snapshot": followup_missing_snapshot,
                "no_configured_competencies": followup_no_competencies,
                "no_mapped_evidence": followup_no_mappings,
                "no_usable_score": followup_no_usable_score,
                "scoring_error": followup_scoring_error,
                "definition": (
                    "Completed mock-drive attempts that did not produce a usable "
                    "competency readiness score, each counted once under a single "
                    "reason: no pinned snapshot, no configured competencies, no "
                    "mapped evidence, no usable score, or a scoring error. Missing "
                    "evidence is never counted as a zero. Counts are attempts "
                    "(contexts), not candidates."
                ),
            },
        },
        "assessment_performance": assessment_performance,
        "drive_activity": drive_activity,
        "kpis": {
            "average_readiness": average_readiness,
            "attempt_improvement": attempt_improvement,
            "threshold_percentage": threshold_percentage,
            "placement_rate": placement_rate,
        },
        "readiness_over_time": readiness_over_time,
        "readiness_distribution": readiness_distribution,
        "by_drive": drive_rows,
        "by_department": by_department,
        "skill_gaps": skill_gaps,
        "insights": insights,
        "filters": {
            "companies": companies,
            "roles": roles,
            "drive_statuses": statuses,
            "periods": ["7", "30", "90", "all"],
        },
    }
