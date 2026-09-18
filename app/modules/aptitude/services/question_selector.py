"""
Question Selector

Responsible only for retrieving questions from the database
based on a given difficulty level.

No business logic should exist here.
"""

import random
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func

from app.models.aptitude import AptitudeQuestion, AptitudeTopic


MCQ_TOPICS = [
    "Quantitative Aptitude",
    "Logical Reasoning",
    "Verbal Ability",
    "Data Interpretation",
]

TECHNICAL_SUBJECT_MAP = {
    "OS": ["Operating Systems"],
    "CN": ["Computer Networks"],
    "OOPS": ["Object-Oriented Programming", "OOPS"],
    "DBMS": ["Database Management Systems", "DBMS"],
    "DSA": ["Data Structures", "DSA", "Data Structures & Algorithms"],
}

ALL_TECHNICAL_TOPICS = [
    "Operating Systems",
    "Computer Networks",
    "Object-Oriented Programming",
    "Database Management Systems",
    "Data Structures",
]


def resolve_topic_names(
    practice_type: Optional[str] = None,
    subject: Optional[str] = None,
    topic: Optional[str] = None,
    is_combined_technical_turn: Optional[bool] = None,
) -> Optional[List[str]]:
    """Determine the list of topic names allowed for the current question query."""
    if topic:
        return [topic]

    p_type = (practice_type or "").lower().strip()
    subj = (subject or "").upper().strip()

    if p_type == "technical":
        if subj in TECHNICAL_SUBJECT_MAP:
            return TECHNICAL_SUBJECT_MAP[subj]
        return ALL_TECHNICAL_TOPICS

    if p_type == "combined":
        # 50% Aptitude, 50% Technical
        if is_combined_technical_turn is True:
            return ALL_TECHNICAL_TOPICS
        elif is_combined_technical_turn is False:
            return MCQ_TOPICS
        else:
            # Random choice if turn not specified
            return ALL_TECHNICAL_TOPICS if random.random() < 0.5 else MCQ_TOPICS

    if p_type == "mcq" or p_type == "aptitude":
        return MCQ_TOPICS

    # If subject was passed directly without explicit practice_type
    if subj in TECHNICAL_SUBJECT_MAP:
        return TECHNICAL_SUBJECT_MAP[subj]

    return None


def select_question_by_difficulty(
    db: Session,
    difficulty: str = "medium",
    practice_type: Optional[str] = None,
    subject: Optional[str] = None,
    topic: Optional[str] = None,
    exclude_ids: Optional[List[int]] = None,
    is_combined_technical_turn: Optional[bool] = None,
) -> Optional[AptitudeQuestion]:
    """
    Fetch a random question matching the given difficulty and practice filters.

    Args:
        db (Session): SQLAlchemy database session
        difficulty (str): easy | medium | hard
        practice_type (str, optional): mcq | technical | combined
        subject (str, optional): OS | CN | OOPS | DBMS | DSA | all
        topic (str, optional): specific topic name
        exclude_ids (list of int, optional): question IDs already used in this round
        is_combined_technical_turn (bool, optional): forces technical vs aptitude for combined round

    Returns:
        AptitudeQuestion | None
    """
    allowed_topics = resolve_topic_names(
        practice_type=practice_type,
        subject=subject,
        topic=topic,
        is_combined_technical_turn=is_combined_technical_turn,
    )

    query = db.query(AptitudeQuestion).filter(AptitudeQuestion.is_active == True)

    if allowed_topics:
        query = query.join(AptitudeTopic, AptitudeQuestion.topic_id == AptitudeTopic.id).filter(
            AptitudeTopic.name.in_(allowed_topics)
        )

    if exclude_ids:
        query = query.filter(~AptitudeQuestion.id.in_(exclude_ids))

    # Try matching the exact requested difficulty
    question = query.filter(AptitudeQuestion.difficulty == difficulty).order_by(func.random()).first()

    # Fallback: if no question at requested difficulty, pick any difficulty within allowed topic
    if not question:
        question = query.order_by(func.random()).first()

    # Last resort fallback if exclude_ids exhausted available questions
    if not question and exclude_ids:
        query_no_exclude = db.query(AptitudeQuestion).filter(AptitudeQuestion.is_active == True)
        if allowed_topics:
            query_no_exclude = query_no_exclude.join(
                AptitudeTopic, AptitudeQuestion.topic_id == AptitudeTopic.id
            ).filter(AptitudeTopic.name.in_(allowed_topics))
        question = query_no_exclude.order_by(func.random()).first()

    return question