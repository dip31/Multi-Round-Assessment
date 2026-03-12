"""
Aptitude Service

Handles core business logic for the Aptitude Round:
- selecting questions
- storing attempts
- calculating results

NOTE:
RL-based difficulty adaptation will be integrated later.
Currently difficulty is fixed to "medium".
"""

from sqlalchemy.orm import Session

from app.models.aptitude import AptitudeQuestion, AptitudeAttempt
from .question_selector import select_question_by_difficulty


def get_next_question(db: Session):
    """
    Fetch the next aptitude question.

    Currently difficulty is static (medium).
    RL engine will replace this later.

    Returns:
        dict
    """

    difficulty = "medium"

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
            "D": question.option_d
        },
        "difficulty": question.difficulty
    }


def submit_answer(
    db: Session,
    round_id: int,
    question_id: int,
    selected_option: str,
    response_time: float
):
    """
    Store a user's answer attempt and return result.

    Args:
        db: database session
        round_id: current aptitude round
        question_id: answered question
        selected_option: A/B/C/D
        response_time: seconds taken

    Returns:
        dict
    """

    question = (
        db.query(AptitudeQuestion)
        .filter(AptitudeQuestion.id == question_id)
        .first()
    )

    if not question:
        return None

    is_correct = question.correct_option == selected_option

    attempt = AptitudeAttempt(
        round_id=round_id,
        question_id=question_id,
        selected_option=selected_option,
        is_correct=is_correct,
        response_time=response_time,
        difficulty=question.difficulty
    )

    db.add(attempt)
    db.commit()

    return {
        "correct": is_correct,
        "correct_option": question.correct_option
    }


def calculate_round_result(db: Session, round_id: int):
    """
    Calculate result summary for a round.

    Returns:
        dict
    """

    attempts = (
        db.query(AptitudeAttempt)
        .filter(AptitudeAttempt.round_id == round_id)
        .all()
    )

    total_questions = len(attempts)

    correct_answers = sum(
        1 for attempt in attempts if attempt.is_correct
    )

    accuracy = (
        correct_answers / total_questions
        if total_questions > 0
        else 0
    )

    return {
        "total_questions": total_questions,
        "correct_answers": correct_answers,
        "accuracy": accuracy
    }