"""
Aptitude Router

Handles all HTTP endpoints related to the Aptitude Round.

Responsibilities:
- Fetch next aptitude question (RL-driven difficulty)
- Submit answer with adaptive difficulty selection
 - Return round result summary

Each endpoint resolves the user's active aptitude round from their
session, ensuring per-user isolation of attempts and scores.
"""

import logging
from typing import Optional
import random
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.assessment import AssessmentRound
from app.models.aptitude import AptitudeAttempt, AptitudeQuestion, AptitudeRoundQuestion, AptitudeTopic
from app.services.session_service import get_user_active_round, get_active_session

from app.modules.aptitude.schemas.aptitude_schema import (
    NextQuestionResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
    RoundResultResponse,
)

from app.modules.aptitude.services.aptitude_service import (
    get_next_question,
    get_current_difficulty,
    submit_answer_and_adapt,
    get_latest_completed_aptitude_result,
)
from app.services.assessment_blueprint_service import (
    configured_question_count,
    difficulty_weights,
    get_session_blueprint_round_config,
    scheduled_round_value,
    topic_weights,
)
from app.services.topic_taxonomy import get_topic_category, normalize_topic, topic_matches_blueprint_group

logger = logging.getLogger(__name__)


def _blueprint_aptitude_diagnostics(
    db: Session,
    active_round: AssessmentRound,
    snapshot: Optional[dict],
    blueprint_round: Optional[dict],
) -> dict:
    """Best-effort snapshot of blueprint/pool/assignment state for logging.

    Captures the exact state that makes a blueprint aptitude round unloadable
    (stale pool, version drift, missing assignments) so a future failure can be
    diagnosed from logs. Never raises - diagnostics must not mask the original
    error.
    """
    diagnostics = {
        "session_id": getattr(active_round, "session_id", None),
        "round_id": getattr(active_round, "id", None),
        "round_status": getattr(active_round, "status", None),
        "blueprint_id": (snapshot or {}).get("blueprint_id"),
        "blueprint_version": (snapshot or {}).get("blueprint_version"),
        "classification": (
            ((snapshot or {}).get("blueprint_data") or {})
            .get("source_provenance", {})
            .get("classification")
        ),
        "configured_question_count": configured_question_count(blueprint_round),
    }
    try:
        from app.services.question_pool_generation_service import (
            question_pool_generation_service as _pool_service,
        )

        registry = _pool_service.complete_pool_for_round(
            db,
            (snapshot or {}).get("blueprint_id"),
            (snapshot or {}).get("blueprint_version"),
            "aptitude",
        )
        diagnostics["pool_status"] = registry.status if registry else None
        diagnostics["pool_validated_count"] = registry.validated_count if registry else 0
        scope = _pool_service.aptitude_pool_scope(db, snapshot)
        diagnostics["pool_scope_size"] = None if scope is None else len(scope)
    except Exception:  # noqa: BLE001 - diagnostics only
        logger.exception("aptitude.diagnostics pool introspection failed")

    try:
        diagnostics["assignment_count"] = (
            db.query(AptitudeRoundQuestion.id)
            .filter(AptitudeRoundQuestion.round_id == active_round.id)
            .count()
        )
        diagnostics["attempt_count"] = (
            db.query(AptitudeAttempt.id)
            .filter(AptitudeAttempt.round_id == active_round.id)
            .count()
        )
    except Exception:  # noqa: BLE001 - diagnostics only
        logger.exception("aptitude.diagnostics count introspection failed")
    return diagnostics


_BLUEPRINT_APTITUDE_ROUND_TYPES = ("aptitude", "mcq", "technical", "combined")


def _session_aptitude_attempt_count(db: Session, session_id: int) -> int:
    """Count aptitude attempts across every aptitude round in a session.

    The active round can be re-created after answers were already recorded
    (round timeout + resume, manual advance, drive re-entry), leaving the
    *current* active round with no attempts while the session still holds them.
    Checking the active round alone turns that valid completion into a false
    "no aptitude questions were completed" error, so this session-wide count is
    the authoritative signal that aptitude work was actually performed.
    """
    return (
        db.query(AptitudeAttempt.id)
        .join(AssessmentRound, AssessmentRound.id == AptitudeAttempt.round_id)
        .filter(
            AssessmentRound.session_id == session_id,
            AssessmentRound.round_type.in_(_BLUEPRINT_APTITUDE_ROUND_TYPES),
        )
        .count()
    )


def _question_matches_blueprint(
    question: AptitudeQuestion,
    round_config: dict,
    question_order: int,
) -> bool:
    configured_topics = topic_weights(round_config)
    target_topic = scheduled_round_value(configured_topics, question_order)
    if target_topic:
        topic_name = question.topic.name if question.topic else ""
        if not topic_matches_blueprint_group(topic_name, target_topic):
            return False
    elif question.topic is None or get_topic_category(
        normalize_topic(question.topic.name) or question.topic.name
    ) != "Aptitude":
        return False

    configured_difficulties = difficulty_weights(round_config)
    target_difficulty = scheduled_round_value(configured_difficulties, question_order)
    return not target_difficulty or question.difficulty.casefold() == target_difficulty.casefold()


def _select_blueprint_aptitude_questions(
    db: Session,
    round_config: dict,
    previously_answered: Optional[list[AptitudeQuestion]] = None,
    question_ids: Optional[list[int]] = None,
) -> list[AptitudeQuestion]:
    question_count = configured_question_count(round_config)
    if question_count is None:
        raise ValueError("The approved aptitude blueprint has no valid question_count.")

    selected: list[AptitudeQuestion] = list(previously_answered or [])
    selected_ids: set[int] = {question.id for question in selected}
    if len(selected) > question_count or len(selected_ids) != len(selected):
        raise ValueError("Existing Aptitude answers cannot be safely resumed against this blueprint.")
    for index, question in enumerate(selected):
        if not _question_matches_blueprint(question, round_config, index):
            raise ValueError(
                "Existing Aptitude answers do not satisfy the pinned blueprint and cannot be resumed safely."
            )
    candidates_query = (
        db.query(AptitudeQuestion)
        .join(AptitudeTopic, AptitudeQuestion.topic_id == AptitudeTopic.id)
        .filter(AptitudeQuestion.is_active.is_(True))
    )
    if question_ids is not None:
        # Pool-only scoping: a complete generated pool is authoritative, so the
        # seeded bank is never mixed in (and never silently substituted). An
        # empty scope yields no candidates and surfaces the usual inventory gap.
        candidates_query = candidates_query.filter(AptitudeQuestion.id.in_(question_ids))
    candidates = candidates_query.order_by(AptitudeQuestion.id).all()
    for index in range(len(selected), question_count):
        eligible = [
            question for question in candidates
            if question.id not in selected_ids
            and _question_matches_blueprint(question, round_config, index)
        ]
        if not eligible:
            target_topic = scheduled_round_value(topic_weights(round_config), index)
            target_difficulty = scheduled_round_value(difficulty_weights(round_config), index)
            raise ValueError(
                "Configured blueprint cannot currently be satisfied by the seeded aptitude question bank: "
                f"unable to assign {question_count} unique questions at position {index + 1} "
                f"(topic={target_topic!r}, difficulty={target_difficulty!r})."
            )
        selected_question = random.choice(eligible)
        selected.append(selected_question)
        selected_ids.add(selected_question.id)

    if len(selected) != question_count or len(selected_ids) != question_count:
        raise ValueError(
            f"Configured blueprint requires {question_count} unique aptitude questions; "
            f"selected {len(selected_ids)}."
        )
    return selected


def _validate_blueprint_aptitude_assignments(
    db: Session, round_config: dict, assignments: list[AptitudeRoundQuestion],
    pool_question_ids: Optional[list[int]] = None,
) -> list[AptitudeQuestion]:
    question_count = configured_question_count(round_config)
    if question_count is None or len(assignments) != question_count:
        raise ValueError(
            "Persisted aptitude assignments do not satisfy the pinned blueprint: "
            f"expected {question_count} assignments, found {len(assignments)}."
        )
    question_ids = [assignment.question_id for assignment in assignments]
    if len(set(question_ids)) != question_count:
        raise ValueError("Persisted aptitude assignments contain duplicate question IDs.")
    if pool_question_ids is not None:
        scoped = set(pool_question_ids)
        if any(question_id not in scoped for question_id in question_ids):
            raise ValueError(
                "Persisted aptitude assignments are outside the generated question pool "
                "and cannot be resumed safely."
            )
    questions_by_id = {
        question.id: question
        for question in db.query(AptitudeQuestion).filter(AptitudeQuestion.id.in_(question_ids)).all()
    }
    if len(questions_by_id) != question_count:
        raise ValueError("One or more persisted aptitude questions are no longer available.")
    ordered_questions = []
    for index, assignment in enumerate(assignments):
        question = questions_by_id[assignment.question_id]
        if not _question_matches_blueprint(question, round_config, index):
            raise ValueError(
                "Persisted aptitude assignments do not satisfy the pinned blueprint: "
                f"question {question.id} violates topic or difficulty at position {index + 1}."
            )
        ordered_questions.append(question)
    return ordered_questions


def _resolve_aptitude_pool_scope(
    db: Session, active_round, round_config: dict
) -> Optional[list[int]]:
    """Resolve the pool-only question scope, or None when no complete pool exists."""
    from app.services.assessment_blueprint_service import get_session_blueprint_round_config
    from app.services.question_pool_generation_service import (
        question_pool_generation_service,
    )

    snapshot = get_session_blueprint_round_config(
        db, active_round.session_id, "aptitude"
    )[0]
    return question_pool_generation_service.aptitude_pool_scope(db, snapshot)


def _ensure_blueprint_aptitude_assignments(
    db: Session, active_round, round_config: dict
) -> tuple[list[AptitudeRoundQuestion], list[AptitudeQuestion]]:
    # Serialize first-time assignment creation for concurrent refresh/retry GETs.
    db.query(AssessmentRound).filter(
        AssessmentRound.id == active_round.id
    ).with_for_update().one()
    assignments = (
        db.query(AptitudeRoundQuestion)
        .filter(AptitudeRoundQuestion.round_id == active_round.id)
        .order_by(AptitudeRoundQuestion.question_order.asc())
        .with_for_update()
        .all()
    )
    pool_question_ids = _resolve_aptitude_pool_scope(db, active_round, round_config)
    if assignments:
        questions = _validate_blueprint_aptitude_assignments(
            db, round_config, assignments, pool_question_ids=pool_question_ids
        )
        return assignments, questions

    # Selection completes and validates in memory before anything is written,
    # so an inventory failure cannot leave a partial assignment set.
    attempts = (
        db.query(AptitudeAttempt)
        .filter(AptitudeAttempt.round_id == active_round.id)
        .order_by(AptitudeAttempt.attempt_number.asc(), AptitudeAttempt.id.asc())
        .all()
    )
    previously_answered_ids = [attempt.question_id for attempt in attempts]
    previously_answered = (
        db.query(AptitudeQuestion)
        .filter(AptitudeQuestion.id.in_(previously_answered_ids))
        .all()
        if previously_answered_ids
        else []
    )
    questions_by_id = {question.id: question for question in previously_answered}
    previously_answered = [
        questions_by_id[question_id]
        for question_id in previously_answered_ids
        if question_id in questions_by_id
    ]
    if len(previously_answered) != len(previously_answered_ids):
        raise ValueError("One or more previously answered Aptitude questions are unavailable.")
    selected = _select_blueprint_aptitude_questions(
        db, round_config, previously_answered=previously_answered,
        question_ids=pool_question_ids,
    )
    assignments = [
        AptitudeRoundQuestion(
            round_id=active_round.id,
            question_id=question.id,
            question_order=index,
        )
        for index, question in enumerate(selected, start=1)
    ]
    db.add_all(assignments)
    db.commit()
    assignments = (
        db.query(AptitudeRoundQuestion)
        .filter(AptitudeRoundQuestion.round_id == active_round.id)
        .order_by(AptitudeRoundQuestion.question_order.asc())
        .all()
    )
    questions = _validate_blueprint_aptitude_assignments(
        db, round_config, assignments, pool_question_ids=pool_question_ids
    )
    return assignments, questions


def _serialize_blueprint_aptitude_question(
    question: AptitudeQuestion, question_number: int, question_count: int
) -> dict:
    topic_name = question.topic.name if question.topic else None
    return {
        "question_id": question.id,
        "question_text": question.question_text,
        "options": {
            "A": question.option_a,
            "B": question.option_b,
            "C": question.option_c,
            "D": question.option_d,
        },
        "difficulty": question.difficulty,
        "topic": topic_name,
        "subject": topic_name,
        "max_questions": question_count,
        "question_number": question_number,
    }

router = APIRouter(
    prefix="/aptitude",
    tags=["Aptitude Round"],
)


def _require_active_round(db: Session, user_id: int):
    """Return the user's active aptitude round or raise 404."""
    active_round = get_user_active_round(db, user_id, round_type="aptitude")
    if active_round is None:
        raise HTTPException(
            status_code=404,
            detail="No active aptitude round. Start a session first via POST /api/v1/session/start",
        )
    return active_round


@router.get(
    "/next-question",
    response_model=NextQuestionResponse,
    response_model_exclude_none=True,
)
def next_question(
    practice_type: Optional[str] = Query(None, description="mcq | technical | combined"),
    subject: Optional[str] = Query(None, description="OS | CN | OOPS | DBMS | DSA | all"),
    topic: Optional[str] = Query(None, description="Specific topic name"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Fetch the next aptitude/practice question for authenticated user.

    Supports practice_type: 'mcq' (Aptitude), 'technical' (CS fundamentals with subject filter),
    or 'combined' (50% Aptitude + 50% Technical).
    """
    active_round = _require_active_round(db, current_user.id)

    snapshot, blueprint_round = get_session_blueprint_round_config(
        db, active_round.session_id, "aptitude"
    )

    if snapshot and blueprint_round:
        try:
            assignments, questions = _ensure_blueprint_aptitude_assignments(
                db, active_round, blueprint_round
            )
        except ValueError as error:
            logger.warning(
                "aptitude.next_question assignment failure user_id=%s error=%s diagnostics=%s",
                current_user.id,
                error,
                _blueprint_aptitude_diagnostics(db, active_round, snapshot, blueprint_round),
            )
            raise HTTPException(status_code=409, detail=str(error))
        answered_count = (
            db.query(AptitudeAttempt.id)
            .filter(AptitudeAttempt.round_id == active_round.id)
            .count()
        )
        if answered_count >= len(assignments):
            logger.info(
                "aptitude.next_question completed user_id=%s answered=%s assignments=%s diagnostics=%s",
                current_user.id,
                answered_count,
                len(assignments),
                _blueprint_aptitude_diagnostics(db, active_round, snapshot, blueprint_round),
            )
            raise HTTPException(status_code=404, detail="Configured aptitude questions completed")
        return _serialize_blueprint_aptitude_question(
            questions[answered_count], answered_count + 1, len(assignments)
        )

    # Get current difficulty from RL session, default to medium for first question
    current_difficulty = get_current_difficulty(db, active_round.id, current_user.id)

    # Check attempts already in this round to prevent duplicate questions
    attempted_ids = [
        row[0]
        for row in db.query(AptitudeAttempt.question_id)
        .filter(AptitudeAttempt.round_id == active_round.id)
        .all()
    ]
    is_combined_turn = (len(attempted_ids) % 2 == 1) if practice_type == "combined" else None

    question = get_next_question(
        db,
        difficulty=current_difficulty,
        practice_type=practice_type,
        subject=subject,
        topic=topic,
        exclude_ids=attempted_ids,
        is_combined_technical_turn=is_combined_turn,
    )

    if not question:
        raise HTTPException(
            status_code=404,
            detail="No aptitude questions available",
        )

    return question


@router.post("/submit-answer", response_model=SubmitAnswerResponse)
def submit_answer_endpoint(
    payload: SubmitAnswerRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Submit an answer and trigger RL-driven difficulty adaptation.

    Returns correctness, reward, next difficulty, and the next question
    pre-selected at the adapted difficulty level.
    """
    active_round = _require_active_round(db, current_user.id)
    active_session = get_active_session(db, current_user.id)

    # G1: Explicit expiry check - reject late answers at submission boundary
    now = datetime.utcnow()
    if active_round.expires_at is not None and now > active_round.expires_at:
        # Mark round as expired and finalize
        _expire_stale_rounds(db, active_session.id)
        raise HTTPException(
            status_code=410,
            detail="Aptitude round has expired. No further answers will be accepted.",
        )

    snapshot, blueprint_round = get_session_blueprint_round_config(
        db, active_round.session_id, "aptitude"
    )
    blueprint_assignments = None
    blueprint_questions = None
    question_number = None
    if snapshot and blueprint_round:
        configured_count = configured_question_count(blueprint_round)
        existing_answer_count = (
            db.query(AptitudeAttempt.id)
            .filter(AptitudeAttempt.round_id == active_round.id)
            .count()
        )
        if configured_count is not None and existing_answer_count >= configured_count:
            raise HTTPException(
                status_code=409,
                detail="Configured aptitude question count has been reached.",
            )
        try:
            blueprint_assignments, blueprint_questions = _ensure_blueprint_aptitude_assignments(
                db, active_round, blueprint_round
            )
        except ValueError as error:
            logger.warning(
                "aptitude.submit_answer assignment failure user_id=%s error=%s diagnostics=%s",
                current_user.id,
                error,
                _blueprint_aptitude_diagnostics(db, active_round, snapshot, blueprint_round),
            )
            raise HTTPException(status_code=409, detail=str(error))
        question_number = existing_answer_count
        if question_number >= len(blueprint_assignments):
            logger.warning(
                "aptitude.submit_answer assignments exhausted user_id=%s answered=%s assignments=%s diagnostics=%s",
                current_user.id,
                existing_answer_count,
                len(blueprint_assignments),
                _blueprint_aptitude_diagnostics(db, active_round, snapshot, blueprint_round),
            )
            raise HTTPException(
                status_code=409,
                detail="Configured aptitude question count has been reached.",
            )
        expected_question = blueprint_questions[question_number]
        if payload.question_id != expected_question.id:
            logger.warning(
                "aptitude.submit_answer assignment mismatch user_id=%s submitted=%s expected=%s "
                "question_number=%s diagnostics=%s",
                current_user.id,
                payload.question_id,
                expected_question.id,
                question_number,
                _blueprint_aptitude_diagnostics(db, active_round, snapshot, blueprint_round),
            )
            raise HTTPException(
                status_code=409,
                detail="The submitted question is not the next assigned question for this blueprint round.",
            )

    result = submit_answer_and_adapt(
        db=db,
        user_id=current_user.id,
        session_id=active_session.id if active_session else 0,
        round_id=active_round.id,
        question_id=payload.question_id,
        selected_option=payload.selected_option,
        response_time=payload.response_time,
        practice_type=payload.practice_type,
        subject=payload.subject,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Question not found",
        )

    if snapshot and blueprint_round and blueprint_assignments is not None:
        answered_count = (
            db.query(AptitudeAttempt.id)
            .filter(AptitudeAttempt.round_id == active_round.id)
            .count()
        )
        if answered_count >= len(blueprint_assignments):
            result["next_question"] = None
        else:
            result["next_question"] = _serialize_blueprint_aptitude_question(
                blueprint_questions[answered_count],
                answered_count + 1,
                len(blueprint_assignments),
            )
    return result


@router.get("/result", response_model=RoundResultResponse)
def get_round_result(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Return summary statistics for the user's most recent completed aptitude session.
    """
    result = get_latest_completed_aptitude_result(db=db, user_id=current_user.id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No completed aptitude session found",
        )

    return result


@router.post("/finish")
def finish_aptitude_round(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Finalize the user's active aptitude round.

    Calculates the score from submitted answers, persists it on the round,
    then marks the round as completed. If the session belongs to a Mock Drive,
    automatically advances to the next configured round.
    Idempotent: safe to call if no active round exists.
    """
    from sqlalchemy import func
    from app.services.session_service import complete_round
    from app.models.assessment import AssessmentRound, AssessmentSession
    from app.services.mock_drive_service import try_advance_mock_drive

    active_session = get_active_session(db, current_user.id)
    is_mock_drive = bool(
        active_session
        and active_session.context
        and active_session.context.mock_drive_id is not None
    )
    active_round = get_user_active_round(db, current_user.id, round_type="aptitude")
    if active_round is None:
        if active_session is not None:
            from app.services.faculty_practice_assignment_service import finalize_faculty_assigned_session
            finalize_faculty_assigned_session(db, current_user.id, active_session.id)
        return {"status": "no_active_round", "is_mock_drive": is_mock_drive}

    # ── Calculate and persist aptitude score BEFORE completing the round ──
    # AptitudeAttempt is imported at module level (line 22)
    total_q = (
        db.query(func.count(AptitudeAttempt.id))
        .filter(AptitudeAttempt.round_id == active_round.id)
        .scalar()
    ) or 0
    snapshot, blueprint_round = get_session_blueprint_round_config(
        db, active_round.session_id, "aptitude"
    )
    if (
        snapshot
        and blueprint_round
        and total_q == 0
        and _session_aptitude_attempt_count(db, active_round.session_id) == 0
    ):
        logger.warning(
            "aptitude.finish blocked: no aptitude questions completed user_id=%s "
            "is_mock_drive=%s diagnostics=%s",
            current_user.id,
            is_mock_drive,
            _blueprint_aptitude_diagnostics(db, active_round, snapshot, blueprint_round),
        )
        raise HTTPException(
            status_code=409,
            detail="Cannot advance this blueprint assessment because no aptitude questions were completed. Resolve the question loading issue and try again.",
        )
    correct_q = (
        db.query(func.count(AptitudeAttempt.id))
        .filter(
            AptitudeAttempt.round_id == active_round.id,
            AptitudeAttempt.is_correct.is_(True),
        )
        .scalar()
    ) or 0
    round_score = round((correct_q / total_q) * 100, 1) if total_q > 0 else 0.0

    # Persist score on the round object before completion
    active_round.score = round_score
    db.commit()
    db.refresh(active_round)

    # Now complete the round (sets status="completed", completed_at)
    complete_round(db, active_round.id)

    # Update session total_score as average of completed round scores
    session_id = active_round.session_id
    avg_score = (
        db.query(func.avg(AssessmentRound.score))
        .filter(
            AssessmentRound.session_id == session_id,
            AssessmentRound.status == "completed",
        )
        .scalar()
    )
    sess = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if sess:
        sess.total_score = float(avg_score or 0.0)
        db.commit()

    from app.services.faculty_practice_assignment_service import finalize_faculty_assigned_attempt
    finalize_faculty_assigned_attempt(db, current_user.id, active_round.id)

    # Advance Mock Drive if applicable (no-op for standalone sessions)
    mock_drive_advance = try_advance_mock_drive(db, active_round.session_id)

    response = {
        "status": "finalized",
        "is_mock_drive": is_mock_drive,
        "round_id": active_round.id,
        "session_id": active_round.session_id,
        "score": round_score,
    }
    if mock_drive_advance:
        response["mock_drive"] = mock_drive_advance
    return response
