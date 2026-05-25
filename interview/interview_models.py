"""
Database models for interview round.
"""
from datetime import datetime
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.sqlite import JSON
from shared.db.database import Base, generate_id


class InterviewSession(Base):
    """Represents an interview session for a candidate."""
    __tablename__ = "interview_sessions"

    id = Column(String, primary_key=True, default=generate_id)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    phase = Column(String, default="HR")  # HR or TECHNICAL
    current_turn = Column(Integer, default=0)
    total_turns = Column(Integer, default=10)
    rl_state = Column(JSON, default=dict)  # RL engine state
    status = Column(String, default="in_progress")  # in_progress, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)


class QuestionPool(Base):
    """Approved question pool for an interview."""
    __tablename__ = "question_pools"

    id = Column(String, primary_key=True, default=generate_id)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    extracted_skills = Column(JSON, default=list)  # Skills from resume
    extracted_projects = Column(JSON, default=dict)  # Projects from resume
    question_pool = Column(JSON, nullable=False)  # List of questions
    admin_approved = Column(Boolean, default=True)  # Auto-approve for demo
    created_at = Column(DateTime, default=datetime.utcnow)


class InterviewTurn(Base):
    """A single turn/question in an interview session."""
    __tablename__ = "interview_turns"

    id = Column(String, primary_key=True, default=generate_id)
    interview_id = Column(String, ForeignKey("interview_sessions.id"), nullable=False)
    turn_number = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    question_difficulty = Column(String)  # EASY, MEDIUM, HARD
    candidate_response = Column(Text)
    response_time_sec = Column(Float)
    content_score = Column(Float)
    final_score = Column(Float)
    intent = Column(String)  # POSITIVE, NEUTRAL, NEGATIVE
    behavioral_snapshot = Column(JSON, default=dict)
    rl_reward = Column(Float)
    is_followup = Column(Boolean, default=False)
    followup_number = Column(Integer, default=0)
    parent_turn_id = Column(String, ForeignKey("interview_turns.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
