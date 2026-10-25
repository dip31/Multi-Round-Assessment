"""
SQLAlchemy ORM models for Phase 4A: Company Historical Data & Pattern Foundation.

CompanyHistoricalData  — raw historical item (file upload or manual entry)
CompanyPattern         — derived structured pattern per company + role
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


# Valid source types for historical data
HISTORICAL_SOURCE_TYPES = ("manual", "file_upload", "pre_seeded")

# Valid file types for uploads
SUPPORTED_FILE_TYPES = ("pdf", "csv", "json", "docx", "xlsx")


class CompanyHistoricalData(Base):
    """A single raw historical data record for a company + role.

    Multiple records can exist per company+role (e.g. drive from 2023, 2024,
    an uploaded PDF, a manually entered past drive, etc.).

    These raw records are the input to pattern extraction.
    They are kept separate from the derived CompanyPattern so the TPO can
    add/remove sources and regenerate the pattern without losing raw data.
    """

    __tablename__ = "company_historical_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ── Company + role key ────────────────────────────────────────────
    # Using string keys (not FK to MockDrive) so historical data can exist
    # for companies that don't yet have a MockDrive created.
    company_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    target_role: Mapped[str] = mapped_column(String(150), nullable=False, index=True)

    # ── Data source ───────────────────────────────────────────────────
    # manual | file_upload | pre_seeded
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")

    # For file_upload: original filename + path on disk
    file_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Label/title for this data item (e.g. "Campus Drive 2024", "Uploaded JD PDF")
    label: Mapped[str] = mapped_column(String(200), nullable=False, default="Historical Drive")

    # ── Structured raw data ───────────────────────────────────────────
    # For manual entry or file-parsed data — stored as-is before normalization.
    # Shape example:
    # {
    #   "year": 2024,
    #   "rounds": ["aptitude", "coding", "interview"],
    #   "topics": ["Arrays", "DSA", "DBMS"],
    #   "question_types": ["MCQ", "Coding"],
    #   "difficulty": "medium",
    #   "duration_minutes": 120,
    #   "notes": "...",
    #   "raw_text": "..."   # from PDF extraction
    # }
    raw_data: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )

    # ── Ownership ─────────────────────────────────────────────────────
    created_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    created_by: Mapped["User"] = relationship("User", lazy="select", foreign_keys=[created_by_id])

    def __repr__(self) -> str:
        return (
            f"<CompanyHistoricalData id={self.id} "
            f"company={self.company_name!r} role={self.target_role!r} "
            f"source={self.source_type!r}>"
        )


class CompanyPattern(Base):
    """Derived structured assessment pattern for a company + role.

    Computed from one or more CompanyHistoricalData records using
    rule-based aggregation. Stored separately so it can be regenerated
    without losing the raw source data.

    One pattern per (company_name, target_role) pair — unique constraint.
    """

    __tablename__ = "company_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ── Company + role key ────────────────────────────────────────────
    company_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    target_role: Mapped[str] = mapped_column(String(150), nullable=False, index=True)

    # ── Derived pattern ───────────────────────────────────────────────
    pattern_data: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )

    # How many historical data items were used to compute this pattern
    source_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Ownership (who last regenerated this pattern)
    created_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    created_by: Mapped["User"] = relationship("User", lazy="select", foreign_keys=[created_by_id])

    def __repr__(self) -> str:
        return (
            f"<CompanyPattern id={self.id} "
            f"company={self.company_name!r} role={self.target_role!r} "
            f"sources={self.source_count}>"
        )


class CompanyBlueprint(Base):
    """Phase 4B: Assessment Blueprint derived from an Approved CompanyPattern.

    Stores the TPO-reviewable assessment blueprint specification:
    - Enabled assessment rounds & sequence
    - Time limit and question counts per round
    - Topic distribution & weights
    - Difficulty distribution
    - Evidence source references & confidence ratings
    - Status: 'draft' | 'approved'
    """

    __tablename__ = "company_blueprints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ── Company + role key ────────────────────────────────────────────
    company_name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    target_role: Mapped[str] = mapped_column(String(150), nullable=False, index=True)

    # Status: 'draft' | 'approved' | 'needs_revision'
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # ── Structured Blueprint Data ─────────────────────────────────────
    # Shape:
    # {
    #   "company_name": "Google",
    #   "target_role": "Software Engineer",
    #   "status": "draft",
    #   "version": 1,
    #   "confidence_level": "high",
    #   "confidence_score": 0.85,
    #   "evidence_sources_count": 3,
    #   "overall_difficulty": "hard",
    #   "rounds": [
    #     {
    #       "round_type": "aptitude",
    #       "round_order": 1,
    #       "round_name": "Aptitude Assessment",
    #       "time_limit_minutes": 60,
    #       "question_count": 30,
    #       "difficulty_distribution": {"easy": 0.2, "medium": 0.5, "hard": 0.3},
    #       "question_types": ["MCQ"],
    #       "topics": [{"topic": "...", "weight_pct": 40.0, "category": "Aptitude"}],
    #       "confidence_level": "high",
    #       "is_default_fallback": False
    #     },
    #     ...
    #   ],
    #   "source_references": [...]
    # }
    blueprint_data: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )

    confidence_level: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    evidence_sources_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ── Review & Approval ─────────────────────────────────────────────
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # ── Ownership ─────────────────────────────────────────────────────
    created_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    created_by: Mapped["User"] = relationship("User", lazy="select", foreign_keys=[created_by_id])
    reviewed_by: Mapped[Optional["User"]] = relationship(
        "User", lazy="select", foreign_keys=[reviewed_by_id]
    )

    def __repr__(self) -> str:
        return (
            f"<CompanyBlueprint id={self.id} "
            f"company={self.company_name!r} role={self.target_role!r} "
            f"status={self.status!r} v={self.version}>"
        )
