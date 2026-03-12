"""
Question Selector

Responsible only for retrieving questions from the database
based on a given difficulty level.

No business logic should exist here.
"""

from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func

from app.models.aptitude import AptitudeQuestion


def select_question_by_difficulty(db: Session, difficulty: str):
    """
    Fetch a random aptitude question matching the given difficulty.

    Args:
        db (Session): SQLAlchemy database session
        difficulty (str): easy | medium | hard

    Returns:
        AptitudeQuestion | None
    """

    question = (
        db.query(AptitudeQuestion)
        .filter(
            AptitudeQuestion.difficulty == difficulty,
            AptitudeQuestion.is_active == True
        )
        .order_by(func.random())  # random question selection
        .first()
    )

    return question