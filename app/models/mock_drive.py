"""
SQLAlchemy ORM model for TPO-managed Mock Drives.

A MockDrive represents a TPO-configured practice placement drive:
company, role, eligibility criteria and selected assessment rounds.

Assessment execution is NOT wired here — this is the configuration store only.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.company_data import CompanyBlueprint


# Valid status values for a MockDrive lifecycle.
MOCK_DRIVE_STATUSES = ("draft", "published", "active", "completed")

# Supported assessment round identifiers.
VALID_ROUNDS = ("aptitude", "coding", "technical_interview", "hr_interview")


class MockDrive(Base):
    """A TPO-configured mock placement drive.

    Lifecycle: draft → published → active → completed.
    Only *draft* drives may be edited or deleted in Phase 2.
    """

    __tablename__ = "mock_drives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # ── Drive identity ─────────────────────────────────────────────────
    company_name: Mapped[str] = mapped_column(String(200), nullable=False)
    target_role: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Status ─────────────────────────────────────────────────────────
    # Values: draft | published | active | completed
    status: Mapped[str] = mapped_column(
        String(20), default="draft", server_default="draft", nullable=False, index=True
    )

    # ── Drive-specific eligibility ─────────────────────────────────────
    minimum_cgpa: Mapped[float] = mapped_column(Float, default=6.0, nullable=False)
    maximum_backlogs: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # List of branch strings, e.g. ["Computer Science", "Information Technology"]
    eligible_branches: Mapped[dict | list] = mapped_column(
        JSONB, default=list, server_default="[]", nullable=False
    )

    # ── Assessment round configuration ────────────────────────────────
    # Dict with boolean flags, e.g.:
    # {"aptitude": true, "coding": true, "technical_interview": false, "hr_interview": false}
    selected_rounds: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    # Per-round assessment settings selected for this drive. Keys use VALID_ROUNDS;
    # values follow the existing blueprint round configuration contract.
    round_configurations: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )

    # ── Blueprint reference (Phase 4C Part 1) ─────────────────────────
    blueprint_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("company_blueprints.id", ondelete="SET NULL"), nullable=True, index=True
    )
    blueprint_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    blueprint_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # ── Ownership ─────────────────────────────────────────────────────
    created_by_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # ── Timestamps ────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # ── Relationships ─────────────────────────────────────────────────
    created_by: Mapped["User"] = relationship("User", lazy="select", foreign_keys=[created_by_id])
    blueprint: Mapped[Optional["CompanyBlueprint"]] = relationship("CompanyBlueprint", lazy="select", foreign_keys=[blueprint_id])

    @property
    def rounds(self) -> list[str]:
        """Return the drive's configured rounds in authoritative order."""
        from app.services.mock_drive_service import _enabled_rounds_in_order
        return _enabled_rounds_in_order(self)

    def __repr__(self) -> str:
        return (
            f"<MockDrive id={self.id} company={self.company_name!r} "
            f"role={self.target_role!r} status={self.status!r}>"
        )
