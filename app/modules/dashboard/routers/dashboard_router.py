"""Role-scoped dashboard aggregation endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.database.db import get_db
from app.models.assessment import AssessmentSession
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["Dashboards"])


def _empty_dashboard(user: User) -> dict:
    initials = "".join(part[0] for part in user.name.split()[:2]).upper()
    return {
        "profile": {"id": user.id, "name": user.name, "initials": initials, "email": user.email},
        "readiness": None,
        "stats": [
            {"id": "assessments-taken", "label": "Assessments taken", "value": 0, "unit": None, "delta": None, "trend": "flat", "hint": "No completed assessments yet"},
            {"id": "avg-score", "label": "Average score", "value": None, "unit": "%", "delta": None, "trend": "flat", "hint": "Complete an assessment to see your score"},
            {"id": "practice-hours", "label": "Practice hours", "value": None, "unit": "h", "delta": None, "trend": "flat", "hint": "No practice activity yet"},
            {"id": "batch-percentile", "label": "Batch percentile", "value": None, "unit": "th", "delta": None, "trend": "flat", "hint": "Not available yet"},
        ],
        "rounds": [],
        "performanceTrend": [],
        "skills": [],
        "upcoming": [],
        "recommendations": [],
        "activity": [],
        "alerts": [],
    }


def _student_dashboard(db: Session, user: User) -> dict:
    payload = _empty_dashboard(user)
    sessions = (
        db.query(AssessmentSession)
        .filter(AssessmentSession.user_id == user.id)
        .order_by(AssessmentSession.started_at.desc())
        .all()
    )
    rounds = [round_item for session in sessions for round_item in session.rounds]
    completed = [item for item in rounds if item.status == "completed"]
    scored = [item.score for item in completed if item.score is not None and item.score > 0]
    payload["stats"][0]["value"] = len(completed)
    if scored:
        payload["stats"][1]["value"] = round(sum(scored) / len(scored), 2)
    payload["rounds"] = [
        {
            "id": item.id,
            "roundType": item.round_type,
            "title": item.round_type.title(),
            "description": "",
            "status": item.status,
            "score": item.score if item.status == "completed" else None,
            "maxScore": 100,
            "durationMinutes": 30,
            "questionsAttempted": 0,
            "questionsTotal": item.max_questions,
            "attemptedAt": item.started_at.isoformat() if item.started_at else None,
            "route": {"aptitude": "/aptitude", "coding": "/coding", "interview": "/resume-upload"}.get(item.round_type),
        }
        for item in rounds
    ]
    active = next((session for session in sessions if session.status == "in_progress"), None)
    if active:
        payload["activeAssessment"] = {
            "id": active.id,
            "status": active.status,
            "rounds": len(active.rounds),
            "completedRounds": sum(item.status == "completed" for item in active.rounds),
        }
    return payload


@router.get("/{role}")
def dashboard(
    role: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return data only for the authenticated user's own role dashboard."""
    if role not in {"student", "faculty", "tpo"}:
        raise HTTPException(status_code=404, detail="Unknown dashboard role")
    if current_user.role != role:
        raise HTTPException(status_code=403, detail="Dashboard role does not match authenticated user")
    return _student_dashboard(db, current_user) if role == "student" else _empty_dashboard(current_user)
