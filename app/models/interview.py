"""
SQLAlchemy ORM models for interview round tables.

Maps to the following PostgreSQL tables:
- interview_sessions
- approved_question_pools
- interview_turns
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database.base import Base


class InterviewSession(Base):
    """Represents an interview session for a candidate.
    
    Columns mirror the ``interview_sessions`` table.
    """

    __tablename__ = "interview_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    round_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("assessment_rounds.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    phase: Mapped[str] = mapped_column(String(20), server_default="HR", nullable=False)
    current_turn: Mapped[int] = mapped_column(Integer, server_default="0", nullable=False)
    total_turns: Mapped[int] = mapped_column(Integer, server_default="10", nullable=False)
    rl_state: Mapped[Dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), server_default="ACTIVE", nullable=False)
    completion_reason: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )  # ALL_QUESTIONS_COMPLETED | USER_SUBMITTED | TIME_EXPIRED
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=True)

    # ── Interviewer presentation ──────────────────────────────────────
    # Which interviewer persona the candidate chose. Nullable on purpose:
    # sessions created before interviewer selection existed have NULL, and
    # NULL resolves to the default profile rather than being an error. Stored
    # as a plain slug with no foreign key because the roster lives in
    # app/modules/interview/config/interviewer_profiles.py, not in a table.
    #
    # This is presentation only — it must never be read by scoring, the
    # follow-up policy, difficulty selection, or the RL state.
    interviewer_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # ── Retell integration ────────────────────────────────────────────
    # Maps EDI5 interview session to Retell call for real-time voice transport.
    # Nullable - only populated when using Retell voice provider.
    retell_call_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    retell_agent_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # ── Personalization metadata (added for question personalization feature) ──
    extraction_confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    retrieval_success_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    question_personalization_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    personalization_metadata: Mapped[Dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    follow_up_quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    personalization_warnings: Mapped[List[str] | None] = mapped_column(JSONB, nullable=True)

    # ── Relationships ─────────────────────────────────────────────────
    turns: Mapped[list["InterviewTurn"]] = relationship(
        "InterviewTurn",
        back_populates="interview",
        cascade="all, delete-orphan",
        lazy="select",
    )

    @property
    def rl_state_dict(self) -> Dict[str, Any]:
        """Get rl_state as a dict."""
        return self.rl_state or {}

    @rl_state_dict.setter
    def rl_state_dict(self, value: Dict[str, Any]) -> None:
        """Set rl_state from a dict."""
        self.rl_state = value

    def __repr__(self) -> str:
        return f"<InterviewSession id={self.id} session_id={self.session_id} phase={self.phase!r}>"


class ApprovedQuestionPool(Base):
    """Represents an approved question pool for an interview.
    
    Columns mirror the ``approved_question_pools`` table.
    """

    __tablename__ = "approved_question_pools"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("assessment_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extracted_skills: Mapped[List[str]] = mapped_column(JSONB, server_default=text("'[]'"), nullable=False)
    extracted_projects: Mapped[Dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"), nullable=False)
    question_pool: Mapped[List[Dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    admin_approved: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False, index=True)
    approved_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    detected_role: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=True)

    @property
    def extracted_skills_list(self) -> List[str]:
        return self.extracted_skills or []

    @extracted_skills_list.setter
    def extracted_skills_list(self, value: List[str]) -> None:
        self.extracted_skills = value

    @property
    def extracted_projects_dict(self) -> Dict[str, Any]:
        return self.extracted_projects or {}

    @extracted_projects_dict.setter
    def extracted_projects_dict(self, value: Dict[str, Any]) -> None:
        self.extracted_projects = value

    @property
    def question_pool_list(self) -> List[Dict[str, Any]]:
        return self.question_pool or []

    @question_pool_list.setter
    def question_pool_list(self, value: List[Dict[str, Any]]) -> None:
        self.question_pool = value

    def __repr__(self) -> str:
        return f"<ApprovedQuestionPool id={self.id} session_id={self.session_id} approved={self.admin_approved}>"


class InterviewTurn(Base):
    """Represents a single turn/question in an interview session.
    
    Columns mirror the ``interview_turns`` table.
    """

    __tablename__ = "interview_turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    interview_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    turn_number: Mapped[int] = mapped_column(Integer, nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_difficulty: Mapped[str | None] = mapped_column(String(10), nullable=True)
    candidate_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_time_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    content_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    final_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    intent: Mapped[str | None] = mapped_column(String(10), nullable=True)
    behavioral_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'"), nullable=False)
    rl_reward: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_followup: Mapped[bool] = mapped_column(Boolean, server_default=text("false"), nullable=False)
    followup_number: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    parent_turn_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("interview_turns.id"), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=True)

    # ── Personalization metadata (added for question personalization feature) ──
    personalization_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    question_grounding_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    answer_classification: Mapped[Dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    followup_grounding_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    followup_targeted_aspect: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────
    interview: Mapped["InterviewSession"] = relationship(
        "InterviewSession",
        back_populates="turns",
        lazy="select",
    )

    @property
    def behavioral_snapshot_dict(self) -> Dict[str, Any]:
        return self.behavioral_snapshot or {}

    @behavioral_snapshot_dict.setter
    def behavioral_snapshot_dict(self, value: Dict[str, Any]) -> None:
        self.behavioral_snapshot = value

    def __repr__(self) -> str:
        return f"<InterviewTurn id={self.id} interview_id={self.interview_id} turn={self.turn_number}>"


class ProctoringViolation(Base):
    """Represents a proctoring violation detected during an interview session.
    
    Columns mirror the ``proctoring_violations`` table.
    """

    __tablename__ = "proctoring_violations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("interview_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    face_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    violation_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        server_default=func.now(),
        nullable=True,
    )

    @property
    def metadata_dict(self) -> Optional[Dict[str, Any]]:
        return self.violation_metadata

    @metadata_dict.setter
    def metadata_dict(self, value: Optional[Dict[str, Any]]) -> None:
        self.violation_metadata = value

    def __repr__(self) -> str:
        return f"<ProctoringViolation id={self.id} session_id={self.session_id} event_type={self.event_type!r}>"


class DynamicInterviewer(Base):
    """Represents a dynamically created interviewer with Retell integration.
    
    Stores interviewer configuration and Retell resource IDs.
    Created by admins via the frontend interviewer management UI.
    """

    __tablename__ = "dynamic_interviewers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # ── Interviewer identity ──────────────────────────────────────────
    # Stable slug used as interviewer_id in InterviewSession
    slug: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    tagline: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # ── Personality & speaking style ──────────────────────────────────
    personality: Mapped[str] = mapped_column(Text, nullable=False)
    speaking_style: Mapped[str] = mapped_column(Text, nullable=False)
    greeting: Mapped[str] = mapped_column(Text, nullable=False)
    
    # ── Avatar & visual ───────────────────────────────────────────────
    avatar_initials: Mapped[str] = mapped_column(String(10), nullable=False)
    accent: Mapped[str] = mapped_column(String(20), nullable=False)  # Tailwind color family
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # ── Voice configuration ───────────────────────────────────────────
    voice_id: Mapped[str] = mapped_column(String(100), nullable=False)
    voice_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    voice_provider: Mapped[str] = mapped_column(String(50), default="retell", nullable=False)
    language_code: Mapped[str] = mapped_column(String(10), default="en-US", nullable=False)
    pace: Mapped[float] = mapped_column(Float, default=0.95, nullable=False)
    
    # ── Retell integration ────────────────────────────────────────────
    # Retell LLM ID (created first, then used by Agent)
    retell_llm_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Retell Agent ID (used for web calls)
    retell_agent_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    
    # ── Status & metadata ─────────────────────────────────────────────
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), server_default=func.now(), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), server_default=func.now(), onupdate=func.now(), nullable=True)

    def to_interviewer_profile(self):
        """Convert to a format compatible with InterviewerProfile for the frontend."""
        from app.modules.interview.config import interviewer_profiles
        from app.modules.interview.config.interviewer_profiles import (
            InterviewerProfile, VoiceSettings, PersonaSettings
        )
        
        voice = VoiceSettings(
            speaker=self.voice_id,
            model=self.voice_model or "bulbul:v3",
            language_code=self.language_code,
            pace=self.pace,
        )
        
        persona = PersonaSettings(
            traits=tuple(self.personality.split(", ")) if self.personality else (),
            transition_hint=self.speaking_style if self.speaking_style else None,
        )
        
        return InterviewerProfile(
            id=self.slug,
            name=self.name,
            title=self.title,
            tagline=self.tagline,
            avatar_initials=self.avatar_initials,
            accent=self.accent,
            voice=voice,
            persona=persona,
            greeting=self.greeting,
        )
