"""
Aptitude Service

Handles core business logic for the Aptitude Round:
- selecting questions (RL-driven difficulty)
- storing attempts
- adaptive difficulty via Q-Learning
- calculating results
"""

from collections import defaultdict
from datetime import datetime
from typing import Optional

from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload

from app.models.aptitude import AptitudeQuestion, AptitudeAttempt
from app.models.rl import RLAttemptLog
from app.models.assessment import AssessmentRound, AssessmentSession
from app.models.proctoring import ProctoringEvent
from app.models.advanced_proctoring import AdvancedProctoringEvent
from app.modules.aptitude.services.question_selector import select_question_by_difficulty
from app.modules.aptitude.rl_engine import (
    build_state,
    calculate_reward,
    select_action,
    update_q_table,
    apply_policy,
    log_attempt,
)
from app.models.aptitude import RLSession
from app.modules.aptitude.rl_engine.reward_calculator import DEFAULT_TIME_LIMIT


DIFFICULTY_ORDER = {
    "easy": 1,
    "medium": 2,
    "hard": 3,
}


def _normalize_difficulty(value: Optional[str]) -> str:
    if value in DIFFICULTY_ORDER:
        return value
    return "medium"


def _difficulty_bucket_template() -> dict[str, dict[str, int]]:
    return {
        "easy": {"correct": 0, "total": 0},
        "medium": {"correct": 0, "total": 0},
        "hard": {"correct": 0, "total": 0},
    }


def _attempt_accuracy(total_questions: int, correct_answers: int) -> float:
    if total_questions <= 0:
        return 0.0
    return round((correct_answers / total_questions) * 100, 1)


def _count_proctoring_event(event_type: str, counts: dict[str, int]) -> None:
    normalized = (event_type or "").lower()
    if normalized in {"tab_switch"}:
        counts["tab_switch"] += 1
    elif normalized in {"fullscreen_exit"}:
        counts["fullscreen_exit"] += 1
    elif normalized in {"idle_activity", "idle"}:
        counts["idle_events"] += 1


def _build_completed_result_from_attempts(
    attempts: list[AptitudeAttempt],
) -> tuple[
    int,
    int,
    float,
    float,
    dict[str, dict[str, int]],
    list[dict],
    list[dict],
    dict[str, int],
    dict[str, list[float]],
    dict[str, int],
]:
    total_questions = len(attempts)
    correct_answers = sum(1 for attempt in attempts if attempt.is_correct)
    accuracy = _attempt_accuracy(total_questions, correct_answers)

    response_times = [float(attempt.response_time) for attempt in attempts if attempt.response_time is not None]
    avg_response_time = round(sum(response_times) / len(response_times), 1) if response_times else 0.0

    difficulty_stats = _difficulty_bucket_template()
    progression: list[dict] = []
    response_time_items: list[dict] = []
    topic_tracker: dict[str, dict[str, object]] = defaultdict(lambda: {"correct": 0, "total": 0, "times": []})
    rl_counts = {"increases": 0, "decreases": 0}
    proctoring_counts = {"tab_switch": 0, "fullscreen_exit": 0, "idle_events": 0}

    previous_difficulty_value: Optional[int] = None
    highest_difficulty_value = 0
    final_difficulty = "medium"

    for attempt in attempts:
        difficulty = _normalize_difficulty(attempt.difficulty)
        difficulty_value = DIFFICULTY_ORDER[difficulty]
        highest_difficulty_value = max(highest_difficulty_value, difficulty_value)
        final_difficulty = difficulty

        difficulty_stats[difficulty]["total"] += 1
        if attempt.is_correct:
            difficulty_stats[difficulty]["correct"] += 1

        progression.append(
            {
                "question": attempt.attempt_number,
                "difficulty": difficulty,
                "correct": bool(attempt.is_correct),
            }
        )

        response_time_items.append(
            {
                "question": attempt.attempt_number,
                "time": round(float(attempt.response_time or 0.0), 1),
            }
        )

        topic_name = "Unknown"
        if attempt.question and attempt.question.topic and attempt.question.topic.name:
            topic_name = attempt.question.topic.name

        topic_entry = topic_tracker[topic_name]
        topic_entry["total"] = int(topic_entry["total"]) + 1
        if attempt.is_correct:
            topic_entry["correct"] = int(topic_entry["correct"]) + 1
        if attempt.response_time is not None:
            topic_entry["times"].append(float(attempt.response_time))

        if previous_difficulty_value is not None:
            if difficulty_value > previous_difficulty_value:
                rl_counts["increases"] += 1
            elif difficulty_value < previous_difficulty_value:
                rl_counts["decreases"] += 1
        previous_difficulty_value = difficulty_value

    return (
        total_questions,
        correct_answers,
        accuracy,
        avg_response_time,
        difficulty_stats,
        progression,
        response_time_items,
        rl_counts,
        topic_tracker,
        proctoring_counts,
    )


def _collect_session_proctoring_counts(db: Session, session_id: int) -> dict[str, int]:
    counts = {"tab_switch": 0, "fullscreen_exit": 0, "idle_events": 0}

    for event_type, in (
        db.query(ProctoringEvent.event_type).filter(ProctoringEvent.session_id == session_id).all()
    ):
        _count_proctoring_event(event_type, counts)

    for event_type, in (
        db.query(AdvancedProctoringEvent.event_type).filter(AdvancedProctoringEvent.session_id == session_id).all()
    ):
        _count_proctoring_event(event_type, counts)

    return counts


def _fetch_latest_completed_aptitude_round(db: Session, user_id: int) -> tuple[Optional[AssessmentSession], Optional[AssessmentRound]]:
    session = (
        db.query(AssessmentSession)
        .join(AssessmentRound, AssessmentRound.session_id == AssessmentSession.id)
        .filter(
            AssessmentSession.user_id == user_id,
            AssessmentSession.status == "completed",
            AssessmentRound.round_type == "aptitude",
            AssessmentRound.status == "completed",
        )
        .order_by(
            AssessmentSession.completed_at.desc().nullslast(),
            AssessmentSession.id.desc(),
        )
        .first()
    )

    if session is None:
        return None, None

    aptitude_round = (
        db.query(AssessmentRound)
        .filter(
            AssessmentRound.session_id == session.id,
            AssessmentRound.round_type == "aptitude",
            AssessmentRound.status == "completed",
        )
        .order_by(
            AssessmentRound.completed_at.desc().nullslast(),
            AssessmentRound.id.desc(),
        )
        .first()
    )

    return session, aptitude_round


def get_latest_completed_aptitude_result(db: Session, user_id: int) -> Optional[dict]:
    """Build the analytics payload for the most recent completed aptitude session."""

    current_session, current_round = _fetch_latest_completed_aptitude_round(db, user_id)
    if current_session is None or current_round is None:
        return None

    attempts = (
        db.query(AptitudeAttempt)
        .options(joinedload(AptitudeAttempt.question).joinedload(AptitudeQuestion.topic))
        .filter(AptitudeAttempt.round_id == current_round.id)
        .order_by(AptitudeAttempt.attempt_number.asc())
        .all()
    )

    (
        total_questions,
        correct_answers,
        accuracy,
        avg_response_time,
        difficulty_stats,
        progression,
        response_times,
        rl_counts,
        topic_tracker,
        _proctoring_counts_placeholder,
    ) = _build_completed_result_from_attempts(attempts)

    completed_rows = (
        db.query(
            AssessmentSession.id.label("session_id"),
            AssessmentSession.user_id.label("user_id"),
            AssessmentSession.completed_at.label("session_completed_at"),
            AssessmentRound.id.label("round_id"),
            AssessmentRound.completed_at.label("round_completed_at"),
            func.count(AptitudeAttempt.id).label("attempt_count"),
            func.coalesce(func.sum(case((AptitudeAttempt.is_correct.is_(True), 1), else_=0)), 0).label("correct_count"),
        )
        .join(AssessmentRound, AssessmentRound.session_id == AssessmentSession.id)
        .outerjoin(AptitudeAttempt, AptitudeAttempt.round_id == AssessmentRound.id)
        .filter(
            AssessmentSession.status == "completed",
            AssessmentRound.round_type == "aptitude",
            AssessmentRound.status == "completed",
        )
        .group_by(
            AssessmentSession.id,
            AssessmentSession.user_id,
            AssessmentSession.completed_at,
            AssessmentRound.id,
            AssessmentRound.completed_at,
        )
        .all()
    )

    latest_by_user: dict[int, dict] = {}
    for row in completed_rows:
        total = int(row.attempt_count or 0)
        correct = int(row.correct_count or 0)
        score = _attempt_accuracy(total, correct)
        candidate = {
            "session_id": row.session_id,
            "session_completed_at": row.session_completed_at or datetime.min,
            "round_id": row.round_id,
            "round_completed_at": row.round_completed_at or datetime.min,
            "score": score,
        }

        existing = latest_by_user.get(row.user_id)
        if existing is None or (
            candidate["session_completed_at"],
            candidate["round_completed_at"],
            candidate["session_id"],
            candidate["round_id"],
        ) > (
            existing["session_completed_at"],
            existing["round_completed_at"],
            existing["session_id"],
            existing["round_id"],
        ):
            latest_by_user[row.user_id] = candidate

    score_pool = [entry["score"] for entry in latest_by_user.values()]
    current_score = score_pool[0] if len(score_pool) == 1 else accuracy
    if user_id in latest_by_user:
        current_score = latest_by_user[user_id]["score"]

    if not score_pool:
        percentile = 0.0
    elif len(score_pool) == 1:
        percentile = 100.0
    else:
        users_scoring_below = sum(1 for score in score_pool if score < current_score)
        percentile = round((users_scoring_below / len(score_pool)) * 100, 1)

    proctoring_counts = _collect_session_proctoring_counts(db, current_session.id)

    topic_stats = []
    for topic_name, values in sorted(
        topic_tracker.items(),
        key=lambda item: (-int(item[1]["total"]), item[0].lower()),
    ):
        total = int(values["total"])
        correct = int(values["correct"])
        times = values["times"]
        topic_stats.append(
            {
                "topic": topic_name,
                "correct": correct,
                "total": total,
                "accuracy": _attempt_accuracy(total, correct),
                "avg_response_time": round(sum(times) / len(times), 1) if times else 0.0,
            }
        )

    peak_difficulty = max(DIFFICULTY_ORDER, key=lambda key: DIFFICULTY_ORDER[key])
    if progression:
        peak_difficulty = max((item["difficulty"] for item in progression), key=lambda key: DIFFICULTY_ORDER.get(key, 0))

    final_difficulty = progression[-1]["difficulty"] if progression else "medium"

    has_multiple_rounds = len(current_session.rounds) > 1

    return {
        "score": float(correct_answers),
        "total_questions": total_questions,
        "accuracy": accuracy,
        "avg_response_time": avg_response_time,
        "percentile": percentile,
        "has_multiple_rounds": has_multiple_rounds,
        "difficulty_stats": difficulty_stats,
        "progression": progression,
        "response_times": response_times,
        "rl_summary": {
            "increases": rl_counts["increases"],
            "decreases": rl_counts["decreases"],
            "peak_difficulty": peak_difficulty,
            "final_difficulty": final_difficulty,
        },
        "proctoring": proctoring_counts,
        "topic_stats": topic_stats,
    }


def get_current_difficulty(db: Session, round_id: int, user_id: int) -> str:
    """Get the current difficulty level from RL session.
    
    Args:
        db: Active database session.
        round_id: The aptitude round ID.
        user_id: The user ID.
        
    Returns:
        Current difficulty as string (easy/medium/hard).
    """
    # Get the most recent RL session entry to find the last action taken
    latest_rl = (
        db.query(RLSession)
        .filter(RLSession.round_id == round_id)
        .order_by(RLSession.step_number.desc())
        .first()
    )
    
    if latest_rl:
        # The action_taken represents the next difficulty that was selected
        return latest_rl.action_taken
    
    # Default to medium for first question
    return "medium"


def get_next_question(db: Session, difficulty: str = "medium") -> Optional[dict]:
    """Fetch the next aptitude question at the given difficulty.

    Args:
        db: Active database session.
        difficulty: Target difficulty (``"easy"`` | ``"medium"`` | ``"hard"``).
            Defaults to ``"medium"`` for the first question in a session.

    Returns:
        Question dict or ``None`` if no questions are available.
    """
    question = select_question_by_difficulty(db, difficulty)

    if not question:
        return None

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
    }


def _load_attempt_history(db: Session, round_id: int) -> list[dict]:
    """Load past attempts for a round as dicts for the state builder.

    Args:
        db: Active database session.
        round_id: The aptitude round to query.

    Returns:
        List of attempt dicts ordered by attempt_number.
    """
    attempts = (
        db.query(AptitudeAttempt)
        .filter(AptitudeAttempt.round_id == round_id)
        .order_by(AptitudeAttempt.attempt_number.asc())
        .all()
    )

    return [
        {
            "is_correct": bool(a.is_correct),
            "response_time": float(a.response_time or 0),
            "difficulty": a.difficulty or "medium",
            "topic": None,  # topic tracked when topic_id is populated
        }
        for a in attempts
    ]


def submit_answer(
    db: Session,
    round_id: int,
    question_id: int,
    selected_option: str,
    response_time: float,
) -> Optional[dict]:
    """Store a user's answer and return result (without RL adaptation).

    Used as a simpler fallback. For RL-driven flow, use
    ``submit_answer_and_adapt``.

    Args:
        db: Active database session.
        round_id: Current aptitude round.
        question_id: The answered question.
        selected_option: ``"A"`` / ``"B"`` / ``"C"`` / ``"D"``.
        response_time: Seconds taken.

    Returns:
        Result dict or ``None`` if question not found.
    """
    question = (
        db.query(AptitudeQuestion)
        .filter(AptitudeQuestion.id == question_id)
        .first()
    )

    if not question:
        return None

    is_correct = question.correct_option == selected_option

    existing_count = (
        db.query(AptitudeAttempt)
        .filter(AptitudeAttempt.round_id == round_id)
        .count()
    )

    attempt = AptitudeAttempt(
        round_id=round_id,
        question_id=question_id,
        attempt_number=existing_count + 1,
        selected_option=selected_option,
        is_correct=is_correct,
        response_time=response_time,
        difficulty=question.difficulty,
    )

    db.add(attempt)
    db.commit()

    return {
        "correct": is_correct,
        "correct_option": question.correct_option,
    }


def submit_answer_and_adapt(
    db: Session,
    user_id: int,
    session_id: int,
    round_id: int,
    question_id: int,
    selected_option: str,
    response_time: float,
) -> Optional[dict]:
    """Submit answer, run RL engine, and return result with next difficulty.

    Full flow:
        1. Store attempt in DB
        2. Build RL state from attempt history
        3. Calculate reward
        4. Select next action via epsilon-greedy
        5. Apply policy guard rails → next difficulty
        6. Update Q-table (Bellman equation)
        7. Log attempt for audit / future DQN replay
        8. Return result + RL metadata

    Args:
        db: Active database session.
        user_id: Authenticated user ID.
        session_id: Current assessment session ID.
        round_id: Current aptitude round ID.
        question_id: The answered question ID.
        selected_option: ``"A"`` / ``"B"`` / ``"C"`` / ``"D"``.
        response_time: Seconds taken.

    Returns:
        Result dict with ``correct``, ``correct_option``, ``next_difficulty``,
        ``reward``, and ``next_question`` fields.  ``None`` if question not found.
    """
    # ── 0. Fetch question ─────────────────────────────────────────────
    question = (
        db.query(AptitudeQuestion)
        .filter(AptitudeQuestion.id == question_id)
        .first()
    )
    if not question:
        return None

    is_correct = question.correct_option == selected_option

    # ── 1. Store attempt ──────────────────────────────────────────────
    existing_count = (
        db.query(AptitudeAttempt)
        .filter(AptitudeAttempt.round_id == round_id)
        .count()
    )

    attempt = AptitudeAttempt(
        round_id=round_id,
        question_id=question_id,
        attempt_number=existing_count + 1,
        selected_option=selected_option,
        is_correct=is_correct,
        response_time=response_time,
        difficulty=question.difficulty,
    )
    db.add(attempt)
    db.flush()  # flush so the new attempt is visible in history query

    # ── 2. Build current RL state ─────────────────────────────────────
    history = _load_attempt_history(db, round_id)
    state_key, state_tuple = build_state(history, question.difficulty)

    # ── 3. Calculate reward ───────────────────────────────────────────
    # Derive a dynamic per-question time limit from the remaining session time
    # and remaining questions in this round (10 questions over 30 minutes, etc.).
    round_obj = db.query(AssessmentRound).filter(AssessmentRound.id == round_id).first()
    session_obj = (
        db.query(AssessmentSession)
        .filter(AssessmentSession.id == session_id)
        .first()
        if session_id
        else None
    )

    # Fallback to DEFAULT_TIME_LIMIT if we cannot compute a dynamic one
    question_time_limit = DEFAULT_TIME_LIMIT
    if round_obj and session_obj:
        remaining_seconds = session_obj.time_remaining_seconds
        remaining_questions = max(round_obj.max_questions - existing_count, 1)
        question_time_limit = max(
            5.0,  # don't go below a small minimum window
            remaining_seconds / remaining_questions,
        )

    reward = calculate_reward(
        is_correct=is_correct,
        difficulty=question.difficulty,
        response_time=response_time,
        question_time_limit=question_time_limit,
        correct_streak=state_tuple.correct_streak,
        wrong_streak=state_tuple.wrong_streak,
    )

    # Store reward on the attempt row
    attempt.reward = reward

    # ── 4. Select next action ─────────────────────────────────────────
    action = select_action(user_id, state_key, db)

    # ── 5. Apply policy → next difficulty ─────────────────────────────
    next_difficulty = apply_policy(
        current_difficulty=question.difficulty,
        action=action,
        correct_streak=state_tuple.correct_streak,
        wrong_streak=state_tuple.wrong_streak,
    )

    # ── 6. Build next state and update Q-table ────────────────────────
    next_state_key, _ = build_state(history, next_difficulty)
    update_q_table(user_id, state_key, action, reward, next_state_key, db)

    # ── 6b. Snapshot RL session for this round step ────────────────────
    total_attempts = len(history)
    correct_so_far = sum(1 for h in history if h["is_correct"])
    accuracy_so_far = (correct_so_far / total_attempts) if total_attempts > 0 else 0.0
    avg_response_time = (
        sum(h["response_time"] for h in history) / total_attempts
        if total_attempts > 0
        else 0.0
    )

    rl_session_row = RLSession(
        round_id=round_id,
        step_number=total_attempts,
        prev_difficulty=question.difficulty,
        action_taken=next_difficulty,
        reward_received=reward,
        accuracy_so_far=accuracy_so_far,
        avg_response_time=avg_response_time,
        q_values=None,  # can be populated later with full Q-table snapshot if needed
    )
    db.add(rl_session_row)

    # ── 7. Log attempt (non-blocking) ─────────────────────────────────
    log_attempt(
        user_id=user_id,
        session_id=session_id,
        question_id=question_id,
        difficulty=question.difficulty,
        state_before=state_key,
        action_taken=action,
        reward=reward,
        state_after=next_state_key,
        response_time=response_time,
        is_correct=is_correct,
        db=db,
    )

    # ── 8. Commit all changes ─────────────────────────────────────────
    db.commit()

    # ── 9. Fetch next question at adapted difficulty ──────────────────
    next_q = get_next_question(db, difficulty=next_difficulty)

    return {
        "correct": is_correct,
        "correct_option": question.correct_option,
        "reward": round(reward, 3),
        "next_difficulty": next_difficulty,
        "next_question": next_q,
    }


def calculate_round_result(db: Session, round_id: int) -> dict:
    """Calculate result summary for a round.

    Args:
        db: Active database session.
        round_id: The aptitude round to summarize.

    Returns:
        Dict with stats and RL evaluation data.
    """
    attempts = (
        db.query(AptitudeAttempt)
        .filter(AptitudeAttempt.round_id == round_id)
        .order_by(AptitudeAttempt.attempt_number)
        .all()
    )

    total_questions = len(attempts)
    correct_answers = sum(1 for a in attempts if a.is_correct)
    accuracy = correct_answers / total_questions if total_questions > 0 else 0.0
    average_response_time = sum(a.response_time for a in attempts if a.response_time) / total_questions if total_questions > 0 else 0.0

    longest_correct_streak = 0
    current_streak = 0
    difficulty_progression = []
    answer_review = []
    
    for a in attempts:
        difficulty_progression.append(a.difficulty)
        q = a.question
        answer_review.append(
            {
                "attempt_number": a.attempt_number,
                "question_id": a.question_id,
                "question_text": q.question_text if q else "",
                "difficulty": a.difficulty or (q.difficulty if q else "medium"),
                "selected_option": a.selected_option,
                "correct_option": q.correct_option if q else "",
                "is_correct": bool(a.is_correct),
                "response_time": float(a.response_time) if a.response_time is not None else None,
                "reward": float(a.reward) if a.reward is not None else None,
            }
        )
        if a.is_correct:
            current_streak += 1
            longest_correct_streak = max(longest_correct_streak, current_streak)
        else:
            current_streak = 0

    round_obj = db.query(AssessmentRound).filter(AssessmentRound.id == round_id).first()
    session_id = round_obj.session_id if round_obj else 0

    rl_logs = (
        db.query(RLAttemptLog)
        .filter(RLAttemptLog.session_id == session_id)
        .order_by(RLAttemptLog.id)
        .all()
    )

    rl_report = []
    for log in rl_logs:
        rl_report.append({
            "state": log.state_before or "start",
            "action": log.action_taken or "none",
            "reward": round(log.reward, 2) if log.reward is not None else 0.0,
            "difficulty": log.difficulty or "N/A"
        })

    return {
        "total_questions": total_questions,
        "correct_answers": correct_answers,
        "accuracy": round(accuracy, 4),
        "average_response_time": round(average_response_time, 2),
        "longest_correct_streak": longest_correct_streak,
        "difficulty_progression": difficulty_progression,
        "rl_report": rl_report,
        "answer_review": answer_review,
    }
