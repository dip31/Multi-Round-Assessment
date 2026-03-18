"""
Aptitude Service

Handles core business logic for the Aptitude Round:
- selecting questions (RL-driven difficulty)
- storing attempts
- adaptive difficulty via Q-Learning
- calculating results
"""

from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.sql import func

from app.models.aptitude import AptitudeQuestion, AptitudeAttempt
from app.models.rl import RLAttemptLog
from app.models.assessment import AssessmentRound, AssessmentSession
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
