"""
FastAPI router for TPO Mock Drive management (Phase 2 + 3A/3B).

TPO endpoints (prefix /tpo/mock-drives):
  POST   /                  — create draft
  GET    /                  — list all (TPO/admin)
  GET    /{id}              — retrieve one
  PUT    /{id}              — update draft
  DELETE /{id}              — delete draft
  POST   /{id}/publish      — publish a draft  ← Phase 3A

Student endpoints (prefix /mock-drives):
  GET    /available          — list published drives student is eligible for
  POST   /{id}/start         — start a mock drive session
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.schemas.mock_drive import (
    MockDriveCreate,
    MockDriveResponse,
    MockDriveResultResponse,
    StudentMockDriveHistoryItem,
    MockDriveRosterResponse,
    MockDriveUpdate,
)
from app.services.mock_drive_service import (
    advance_mock_drive_round,
    create_mock_drive,
    delete_mock_drive,
    get_mock_drive,
    get_mock_drive_result,
    get_student_mock_drive_history,
    get_mock_drive_roster,
    get_mock_drive_status,
    list_eligible_mock_drives,
    list_mock_drives,
    publish_mock_drive,
    reprocess_mock_drive_competency_mappings,
    start_mock_drive_session,
    try_advance_mock_drive,
    update_mock_drive,
)

# ── Two separate routers so prefixes don't conflict ───────────────────
router = APIRouter(prefix="/tpo/mock-drives", tags=["TPO Mock Drives"])
student_router = APIRouter(prefix="/mock-drives", tags=["Student Mock Drives"])


# ── RBAC helpers ──────────────────────────────────────────────────────

def _require_tpo_or_admin(current_user: User) -> None:
    if current_user.role not in ("tpo", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires TPO or admin privileges.",
        )


def _require_student(current_user: User) -> None:
    if current_user.role not in ("student",):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is for students only.",
        )


# ── TPO CRUD (Phase 2) ────────────────────────────────────────────────

@router.post("", response_model=MockDriveResponse, status_code=status.HTTP_201_CREATED)
def create_drive(
    payload: MockDriveCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_tpo_or_admin(current_user)
    return create_mock_drive(db=db, payload=payload, created_by_id=current_user.id)


@router.get("", response_model=List[MockDriveResponse])
def list_drives(
    status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_tpo_or_admin(current_user)
    return list_mock_drives(db=db, status_filter=status)


@router.get("/{mock_drive_id}", response_model=MockDriveResponse)
def get_drive(
    mock_drive_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_tpo_or_admin(current_user)
    return get_mock_drive(db=db, mock_drive_id=mock_drive_id)


@router.put("/{mock_drive_id}", response_model=MockDriveResponse)
def update_drive(
    mock_drive_id: int,
    payload: MockDriveUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_tpo_or_admin(current_user)
    return update_mock_drive(db=db, mock_drive_id=mock_drive_id, payload=payload)


@router.delete("/{mock_drive_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_drive(
    mock_drive_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_tpo_or_admin(current_user)
    delete_mock_drive(db=db, mock_drive_id=mock_drive_id)


# ── Phase 3A: Publish ─────────────────────────────────────────────────

@router.post("/{mock_drive_id}/publish", response_model=MockDriveResponse)
def publish_drive(
    mock_drive_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Publish a DRAFT mock drive. Validates completeness before transitioning status."""
    _require_tpo_or_admin(current_user)
    return publish_mock_drive(db=db, mock_drive_id=mock_drive_id)


# ── Phase 4C: Competency mapping recovery ─────────────────────────────

@router.post("/{mock_drive_id}/competency-mapping/reprocess")
def reprocess_competency_mappings(
    mock_drive_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reprocess pending/failed competency mappings for a Mock Drive (TPO/admin).

    Idempotent recovery for completed contexts whose evidence→competency
    mapping is pending, failed, or not yet tracked. Uses pinned snapshots,
    never reruns the assessment, and never changes scores.
    """
    _require_tpo_or_admin(current_user)
    return reprocess_mock_drive_competency_mappings(db=db, mock_drive_id=mock_drive_id)


# ── G4: Derived candidate roster + TPO result access ──────────────────

@router.get("/{mock_drive_id}/roster", response_model=MockDriveRosterResponse)
def get_drive_roster(
    mock_drive_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the derived candidate roster for a Mock Drive (TPO/admin).

    Derived from authoritative AssessmentContext/Session/Round records only;
    no duplicate assignment state and no invented eligibility or scoring.
    """
    _require_tpo_or_admin(current_user)
    return get_mock_drive_roster(db=db, mock_drive_id=mock_drive_id)


@router.get(
    "/{mock_drive_id}/candidates/{student_id}/result",
    response_model=MockDriveResultResponse,
)
def get_candidate_drive_result(
    mock_drive_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return one candidate's consolidated result for a Mock Drive (TPO/admin).

    Grants staff read access to the same persisted, per-candidate result the
    owning candidate sees at ``GET /mock-drives/{id}/result``. Candidate access
    stays separated (this route is staff-only).
    """
    _require_tpo_or_admin(current_user)
    result = get_mock_drive_result(db=db, mock_drive_id=mock_drive_id, student_id=student_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No result found for this candidate on this mock drive.",
        )
    return result


# ── Phase 3B: Student endpoints ───────────────────────────────────────

@student_router.get("/available", response_model=List[MockDriveResponse])
def get_available_drives(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return published MockDrives the authenticated student is eligible for."""
    _require_student(current_user)
    return list_eligible_mock_drives(db=db, student_id=current_user.id)


@student_router.get("/history", response_model=List[StudentMockDriveHistoryItem])
def get_student_drive_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return only mock drives the authenticated student has started."""
    _require_student(current_user)
    return get_student_mock_drive_history(db=db, student_id=current_user.id)


@student_router.post("/{mock_drive_id}/start")
def start_drive(
    mock_drive_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create an AssessmentSession for the student to begin the mock drive."""
    _require_student(current_user)
    return start_mock_drive_session(
        db=db,
        mock_drive_id=mock_drive_id,
        student_id=current_user.id,
    )


@student_router.get("/{mock_drive_id}/status")
def get_drive_status(
    mock_drive_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the current state of the student's mock drive attempt."""
    _require_student(current_user)
    return get_mock_drive_status(
        db=db, mock_drive_id=mock_drive_id, student_id=current_user.id,
    )


@student_router.get("/{mock_drive_id}/result", response_model=MockDriveResultResponse)
def get_drive_result(
    mock_drive_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return drive-scoped round results for the authenticated student.

    Round scores retain their source scales. No cross-round overall score is
    returned because the configured assessment types use incompatible scales.
    """
    _require_student(current_user)
    result = get_mock_drive_result(
        db=db, mock_drive_id=mock_drive_id, student_id=current_user.id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No result found for this mock drive attempt.",
        )
    return result


@student_router.post("/{mock_drive_id}/advance")
def advance_drive(
    mock_drive_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Complete the current round and activate the next enabled round.

    If this was the final round, marks the mock drive as completed.
    """
    _require_student(current_user)
    return advance_mock_drive_round(
        db=db, mock_drive_id=mock_drive_id, student_id=current_user.id,
    )
