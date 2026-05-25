"""
SQLAlchemy ORM models for the recruitment system.
"""
from datetime import datetime, date
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, Date, Boolean, ForeignKey
from shared.db.database import Base, generate_id


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, default=generate_id)
    title = Column(String, nullable=False)
    department = Column(String)
    location = Column(String)
    employment_type = Column(String, default="full-time")
    experience_min = Column(Integer, default=0)
    experience_max = Column(Integer, default=0)
    salary_min = Column(Float)
    salary_max = Column(Float)
    currency = Column(String, default="INR")
    skills = Column(Text)  # JSON array string
    qualification = Column(String)  # Required education level for scoring
    description = Column(Text)  # AI-generated JD
    status = Column(String, default="draft")
    headcount = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(String, primary_key=True, default=generate_id)
    name = Column(String, nullable=False)
    email = Column(String)
    phone = Column(String)
    location = Column(String)
    current_role = Column(String)
    experience_years = Column(Float, default=0)
    skills = Column(Text)  # JSON array string
    education = Column(Text)  # JSON array string
    work_history = Column(Text)  # JSON array string
    resume_url = Column(String)
    source = Column(String, default="upload")
    source_profile_url = Column(String)
    raw_resume_text = Column(Text)
    parsed_data = Column(Text)  # Full JSON from LlamaIndex
    status = Column(String, default="new")
    
    # Stage 3 Screening fields
    job_id = Column(String, ForeignKey("jobs.id"))  # Link to job for screening
    score = Column(Float)  # Overall screening score
    score_breakdown = Column(Text)  # JSON breakdown of scoring components
    is_duplicate = Column(Boolean, default=False)
    merged_into = Column(String)  # ID of original candidate if duplicate
    rejection_reason = Column(String)  # Reason for rejection
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Application(Base):
    __tablename__ = "applications"

    id = Column(String, primary_key=True, default=generate_id)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    status = Column(String, default="applied")
    match_score = Column(Float)
    applied_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Score(Base):
    __tablename__ = "scores"

    id = Column(String, primary_key=True, default=generate_id)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    overall_score = Column(Float, default=0)
    skill_match = Column(Float, default=0)
    experience_match = Column(Float, default=0)
    location_match = Column(Float, default=0)
    education_match = Column(Float, default=0)
    scoring_algorithm = Column(String, default="basic")
    scored_at = Column(DateTime, default=datetime.utcnow)


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(String, primary_key=True, default=generate_id)
    application_id = Column(String, ForeignKey("applications.id"), nullable=False)
    interview_type = Column(String, default="technical")
    scheduled_at = Column(DateTime)
    duration_minutes = Column(Integer, default=60)
    interviewer = Column(String)
    location = Column(String)
    meeting_link = Column(String)
    status = Column(String, default="scheduled")
    feedback = Column(Text)
    rating = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Offer(Base):
    __tablename__ = "offers"

    id = Column(String, primary_key=True, default=generate_id)
    application_id = Column(String, ForeignKey("applications.id"), nullable=False)
    salary_offered = Column(Float)
    currency = Column(String, default="INR")
    benefits = Column(Text)  # JSON array
    start_date = Column(Date)
    offer_letter_url = Column(String)
    status = Column(String, default="pending")
    offered_at = Column(DateTime, default=datetime.utcnow)
    response_deadline = Column(DateTime)
    accepted_at = Column(DateTime)
    rejected_at = Column(DateTime)
    rejection_reason = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class OnboardingTask(Base):
    __tablename__ = "onboarding_tasks"

    id = Column(String, primary_key=True, default=generate_id)
    offer_id = Column(String, ForeignKey("offers.id"), nullable=False)
    task_name = Column(String, nullable=False)
    task_description = Column(Text)
    assigned_to = Column(String)
    due_date = Column(Date)
    status = Column(String, default="pending")
    completed_at = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)


class Communication(Base):
    __tablename__ = "communications"

    id = Column(String, primary_key=True, default=generate_id)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    job_id = Column(String, ForeignKey("jobs.id"))
    communication_type = Column(String, nullable=False)
    direction = Column(String, nullable=False)
    subject = Column(String)
    content = Column(Text)
    sent_at = Column(DateTime, default=datetime.utcnow)
    read_at = Column(DateTime)
    response_required = Column(Boolean, default=False)
    response_deadline = Column(DateTime)
    created_by = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class JobPosting(Base):
    __tablename__ = "job_postings"

    id = Column(String, primary_key=True, default=generate_id)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    platform = Column(String, nullable=False)
    external_id = Column(String)
    post_url = Column(String)
    status = Column(String, default="pending")
    posted_at = Column(DateTime)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(String, primary_key=True, default=generate_id)
    event_type = Column(String, nullable=False)
    agent_name = Column(String, nullable=False)
    entity_type = Column(String)
    entity_id = Column(String)
    details = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)



class ChatbotSession(Base):
    """Stage 5 — Prescreening chatbot sessions"""
    __tablename__ = "chatbot_sessions"
    
    session_id = Column(String, primary_key=True, default=generate_id)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    job_id = Column(String, ForeignKey("jobs.id"), nullable=False)
    token = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    status = Column(String, default="PENDING")  # PENDING, IN_PROGRESS, COMPLETED, EXPIRED
    questions = Column(Text)  # JSON array of questions
    completed_at = Column(DateTime)


class ChatbotAnswer(Base):
    """Stage 5 — Prescreening chatbot answers"""
    __tablename__ = "chatbot_answers"
    
    answer_id = Column(String, primary_key=True, default=generate_id)
    session_id = Column(String, ForeignKey("chatbot_sessions.session_id"), nullable=False)
    question_index = Column(Integer, nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    answered_at = Column(DateTime, default=datetime.utcnow)
    ai_score = Column(String)  # Excellent, Good, Average, Poor
    disqualified = Column(Boolean, default=False)
    reason = Column(Text)
