"""Admin endpoints for performance-driven aptitude question review."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, case, cast, desc, func, inspect, literal, Numeric
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.database.db import get_db
from app.models.admin_question_feedback import AdminQuestionFeedback
from app.models.aptitude import AptitudeAttempt, AptitudeQuestion
from app.models.user import User
from app.modules.aptitude.schemas.admin_question_schema import (
    AdminQuestionActionResponse,
    AdminQuestionDetailResponse,
    AdminQuestionFeedbackRequest,
    AdminQuestionListResponse,
    AdminQuestionStatusUpdateRequest,
)

router = APIRouter(prefix="/admin/questions", tags=["Admin Question Review"])

DIFFICULTY_SORT = case(
    (AptitudeQuestion.difficulty == "easy", 1),
    (AptitudeQuestion.difficulty == "medium", 2),
    (AptitudeQuestion.difficulty == "hard", 3),
    else_=4,
)


def _ensure_admin(current_user: User) -> None:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires admin privileges",
        )


def _insight_from_metrics(accuracy: float, avg_time: float) -> tuple[str, str]:
    # Strict rule priority required by product spec.
    if accuracy < 40:
        return (
            "Students are struggling with this question",
            "too_hard",
        )

    if accuracy > 85 and avg_time < 5:
        return (
            "This question may be too easy",
            "too_easy",
        )

    if avg_time > 15 and 40 <= accuracy <= 85:
        return (
            "Students are taking too long — simplify wording",
            "confusing",
        )

    if accuracy > 85 and avg_time > 10:
        return (
            "High accuracy but slow responses — question may be wordy",
            "confusing",
        )

    return (
        "This question is well-balanced",
        "balanced",
    )


def _recommendation_from_insight(insight_type: str) -> str:
    if insight_type == "balanced":
        return "approve"
    if insight_type in {"too_hard", "too_easy", "confusing"}:
        return "review"
    return "reject"


def _needs_attention(accuracy: float, avg_time: float) -> bool:
    return accuracy < 40 or accuracy > 90 or avg_time > 15


def _build_base_query(db: Session):
    attempts_subquery = (
        db.query(
            AptitudeAttempt.question_id.label("question_id"),
            func.count(AptitudeAttempt.id).label("attempts"),
            func.coalesce(
                func.sum(case((AptitudeAttempt.is_correct.is_(True), 1), else_=0)),
                0,
            ).label("correct_count"),
            func.coalesce(func.avg(AptitudeAttempt.response_time), 0.0).label("avg_time"),
            func.coalesce(func.avg(case((AptitudeAttempt.is_correct.is_(True), 100.0), else_=0.0)), 0.0).label("avg_accuracy_when_served"),
            func.max(AptitudeAttempt.attempted_at).label("last_served"),
        )
        .group_by(AptitudeAttempt.question_id)
        .subquery()
    )

    has_feedback_table = inspect(db.bind).has_table("admin_question_feedback")

    latest_feedback = None
    if has_feedback_table:
        latest_feedback_id = (
            db.query(
                AdminQuestionFeedback.question_id.label("question_id"),
                func.max(AdminQuestionFeedback.id).label("latest_feedback_id"),
            )
            .group_by(AdminQuestionFeedback.question_id)
            .subquery()
        )

        latest_feedback = (
            db.query(
                AdminQuestionFeedback.question_id.label("question_id"),
                AdminQuestionFeedback.action.label("latest_action"),
                AdminQuestionFeedback.suggestion.label("suggestion"),
                AdminQuestionFeedback.created_at.label("feedback_at"),
            )
            .join(
                latest_feedback_id,
                AdminQuestionFeedback.id == latest_feedback_id.c.latest_feedback_id,
            )
            .subquery()
        )

    attempts_value = func.coalesce(attempts_subquery.c.attempts, 0)
    correct_value = func.coalesce(attempts_subquery.c.correct_count, 0)
    avg_time_value = func.coalesce(attempts_subquery.c.avg_time, 0.0)

    accuracy_expr = case(
        (attempts_value > 0, (correct_value * 100.0) / attempts_value),
        else_=0.0,
    )

    if has_feedback_table:
        status_expr = case(
            (latest_feedback.c.latest_action == "review", "needs_review"),
            (AptitudeQuestion.is_active.is_(False), "rejected"),
            else_="approved",
        )
        suggestion_expr = latest_feedback.c.suggestion
    else:
        status_expr = case(
            (AptitudeQuestion.is_active.is_(False), "rejected"),
            else_="approved",
        )
        suggestion_expr = literal(None)

    query = (
        db.query(
            AptitudeQuestion.id.label("id"),
            AptitudeQuestion.question_text.label("question_text"),
            AptitudeQuestion.option_a.label("option_a"),
            AptitudeQuestion.option_b.label("option_b"),
            AptitudeQuestion.option_c.label("option_c"),
            AptitudeQuestion.option_d.label("option_d"),
            AptitudeQuestion.correct_option.label("correct_option"),
            AptitudeQuestion.difficulty.label("difficulty"),
            attempts_value.label("attempts"),
            func.round(cast(accuracy_expr, Numeric(10, 2)), 2).label("accuracy"),
            func.round(cast(avg_time_value, Numeric(10, 2)), 2).label("avg_time"),
            func.round(
                cast(func.coalesce(attempts_subquery.c.avg_accuracy_when_served, 0.0), Numeric(10, 2)),
                2,
            ).label("avg_accuracy_when_served"),
            attempts_subquery.c.last_served.label("last_served"),
            status_expr.label("status"),
            suggestion_expr.label("suggestion"),
        )
        .outerjoin(
            attempts_subquery,
            attempts_subquery.c.question_id == AptitudeQuestion.id,
        )
    )

    if has_feedback_table:
        query = query.outerjoin(
            latest_feedback,
            latest_feedback.c.question_id == AptitudeQuestion.id,
        )

    return query, accuracy_expr, status_expr, attempts_value, avg_time_value


@router.get("", response_model=AdminQuestionListResponse)
def list_questions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    difficulty: str = Query("all"),
    accuracy_range: str = Query("all"),
    status_filter: str = Query("all", alias="status"),
    search: str = Query(""),
    sort_by: str = Query("accuracy"),
    sort_order: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)

    query, accuracy_expr, status_expr, attempts_value, avg_time_value = _build_base_query(db)

    if difficulty in {"easy", "medium", "hard"}:
        query = query.filter(AptitudeQuestion.difficulty == difficulty)

    if accuracy_range == "too_easy":
        query = query.filter(accuracy_expr > 85)
    elif accuracy_range == "balanced":
        query = query.filter(and_(accuracy_expr >= 40, accuracy_expr <= 85))
    elif accuracy_range == "too_hard":
        query = query.filter(accuracy_expr < 40)

    if status_filter in {"approved", "rejected", "needs_review"}:
        query = query.filter(status_expr == status_filter)

    if search:
        lowered = f"%{search.strip().lower()}%"
        query = query.filter(func.lower(AptitudeQuestion.question_text).like(lowered))

    default_sort_order = {
        "difficulty": "asc",
        "attempts": "desc",
        "accuracy": "asc",
        "avg_time": "desc",
    }
    resolved_sort_order = sort_order if sort_order in {"asc", "desc"} else default_sort_order.get(sort_by, "asc")

    if sort_by == "difficulty":
        order_target = DIFFICULTY_SORT
    elif sort_by == "attempts":
        order_target = attempts_value
    elif sort_by == "avg_time":
        order_target = avg_time_value
    else:
        order_target = accuracy_expr

    if resolved_sort_order == "desc":
        query = query.order_by(desc(order_target), AptitudeQuestion.id.asc())
    else:
        query = query.order_by(order_target, AptitudeQuestion.id.asc())

    total = query.count()

    rows = (
        query.offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    questions = [
        {
            "id": row.id,
            "question_text": row.question_text,
            "difficulty": row.difficulty,
            "attempts": int(row.attempts or 0),
            "accuracy": float(row.accuracy or 0.0),
            "avg_time": float(row.avg_time or 0.0),
            "status": row.status,
            "needs_attention": _needs_attention(
                accuracy=float(row.accuracy or 0.0),
                avg_time=float(row.avg_time or 0.0),
            ),
        }
        for row in rows
    ]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "questions": questions,
    }


@router.get("/{question_id}", response_model=AdminQuestionDetailResponse)
def get_question_detail(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)

    query, _accuracy_expr, _status_expr, _attempts_value, _avg_time_value = _build_base_query(db)
    row = query.filter(AptitudeQuestion.id == question_id).first()

    if row is None:
        raise HTTPException(status_code=404, detail="Question not found")

    accuracy = float(row.accuracy or 0.0)
    avg_time = float(row.avg_time or 0.0)
    insight, insight_type = _insight_from_metrics(accuracy=accuracy, avg_time=avg_time)
    recommendation = _recommendation_from_insight(insight_type)

    return {
        "id": row.id,
        "question_text": row.question_text,
        "options": [row.option_a, row.option_b, row.option_c, row.option_d],
        "correct_option": row.correct_option,
        "difficulty": row.difficulty,
        "attempts": int(row.attempts or 0),
        "accuracy": accuracy,
        "avg_time": avg_time,
        "insight": insight,
        "insight_type": insight_type,
        "recommendation": recommendation,
        "rl_data": {
            "in_active_pool": row.status == "approved",
            "times_served": int(row.attempts or 0),
            "last_served": row.last_served,
            "avg_accuracy_when_served": float(row.avg_accuracy_when_served or 0.0),
        },
        "suggestion": row.suggestion,
    }


@router.put("/{question_id}/status", response_model=AdminQuestionActionResponse)
def update_question_status(
    question_id: int,
    payload: AdminQuestionStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)

    question = db.query(AptitudeQuestion).filter(AptitudeQuestion.id == question_id).first()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    question.is_active = payload.status == "approved"

    db.add(
        AdminQuestionFeedback(
            question_id=question_id,
            admin_id=current_user.id,
            action="approve" if payload.status == "approved" else "reject",
            suggestion=None,
        )
    )

    db.commit()

    return {
        "success": True,
        "message": f"Question marked as {payload.status}",
    }


@router.post("/{question_id}/feedback", response_model=AdminQuestionActionResponse)
def submit_question_feedback(
    question_id: int,
    payload: AdminQuestionFeedbackRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_admin(current_user)

    question = db.query(AptitudeQuestion).filter(AptitudeQuestion.id == question_id).first()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    if payload.action == "approve":
        question.is_active = True
    elif payload.action in {"reject", "review"}:
        question.is_active = False

    db.add(
        AdminQuestionFeedback(
            question_id=question_id,
            admin_id=current_user.id,
            action=payload.action,
            suggestion=payload.suggestion.strip(),
        )
    )

    db.commit()

    return {
        "success": True,
        "message": "Feedback saved",
    }
