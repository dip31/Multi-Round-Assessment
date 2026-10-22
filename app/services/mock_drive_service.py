"""
Service layer for TPO Mock Drive CRUD operations.

All business rules (draft-only edits, deletion guard, publish guard,
student eligibility, drive session creation) live here.
"""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.mock_drive import MockDrive, VALID_ROUNDS
from app.models.company_data import CompanyBlueprint
from app.models.profile import StudentProfile
from app.models.assessment_context import AssessmentContext
from app.models.assessment import AssessmentSession, AssessmentRound
from app.models.aptitude import AptitudeAttempt
from app.schemas.mock_drive import MockDriveCreate, MockDriveUpdate
from app.services.assessment_context_service import (
    MODE_MOCK_DRIVE,
    DEFAULT_PRACTICE_POLICY_ID,
)
from app.services.assessment_blueprint_service import (
    configured_question_count,
    get_blueprint_round_config,
    get_drive_blueprint_snapshot,
    get_session_blueprint_round_config,
    snapshot_company_blueprint,
    snapshot_for_assessment_context,
)
from app.services.competency_scoring_service import score_session_competencies

logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────

def _get_or_404(db: Session, mock_drive_id: int) -> MockDrive:
    """Return the MockDrive or raise 404."""
    drive = db.query(MockDrive).filter(MockDrive.id == mock_drive_id).first()
    if not drive:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Mock drive {mock_drive_id} not found.",
        )
    return drive


def _assert_draft(drive: MockDrive, action: str = "modify") -> None:
    """Raise 422 if the drive is not in draft status."""
    if drive.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Cannot {action} mock drive {drive.id!r}: "
                f"only draft drives may be {action}d "
                f"(current status: {drive.status!r})."
            ),
        )


def _validate_and_attach_blueprint(
    db: Session,
    company_name: str,
    target_role: str,
    blueprint_id: Optional[int],
) -> Optional[CompanyBlueprint]:
    """Validate that the blueprint exists, is approved, and matches company + role.

    Raises HTTPException 404 or 422 if invalid.
    """
    if blueprint_id is None:
        return None

    bp = db.query(CompanyBlueprint).filter(CompanyBlueprint.id == blueprint_id).first()
    if not bp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assessment blueprint with ID {blueprint_id} not found.",
        )

    if bp.status != "approved":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Cannot attach blueprint {blueprint_id}: only 'approved' blueprints "
                f"can be linked to a mock drive (current status: '{bp.status}')."
            ),
        )

    # Check company and role match
    if (
        bp.company_name.strip().lower() != company_name.strip().lower()
        or bp.target_role.strip().lower() != target_role.strip().lower()
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                f"Blueprint {blueprint_id} is for '{bp.company_name}' - '{bp.target_role}', "
                f"which does not match mock drive '{company_name}' - '{target_role}'."
            ),
        )

    return bp


def _round_configurations_from_snapshot(
    snapshot: Optional[dict],
    selected_rounds,
) -> dict:
    """Derive the backward-compatible round_configurations cache from a pinned snapshot.

    The blueprint snapshot is the sole runtime authority for round configuration;
    this persisted field is only a derived mirror (blueprint ``time_limit_minutes``
    is exposed here as ``duration_minutes``). Only enabled rounds are included, and
    entries that would fail the request-schema rules are omitted so the cache can
    never round-trip into a 422.
    """
    if not snapshot or not isinstance(snapshot, dict):
        return {}
    if isinstance(selected_rounds, dict):
        enabled = {r for r, on in selected_rounds.items() if on}
    elif isinstance(selected_rounds, list):
        enabled = set(selected_rounds)
    else:
        enabled = set()

    rounds = (snapshot.get("blueprint_data") or {}).get("rounds") or []
    derived: dict = {}
    for round_config in rounds:
        if not isinstance(round_config, dict):
            continue
        round_type = round_config.get("round_type")
        if round_type not in VALID_ROUNDS or round_type not in enabled:
            continue
        difficulty = round_config.get("difficulty_distribution")
        entry = {
            "question_count": round_config.get("question_count"),
            "duration_minutes": round_config.get("time_limit_minutes"),
            "difficulty_distribution": dict(difficulty) if isinstance(difficulty, dict) else None,
        }
        try:
            MockDriveCreate._check_round_configurations(
                {round_type: entry}, {round_type: True}
            )
        except ValueError:
            continue
        derived[round_type] = entry
    return derived


# ── TPO CRUD (Phase 2 + Phase 4C Part 1) ──────────────────────────────

def create_mock_drive(
    db: Session,
    payload: MockDriveCreate,
    created_by_id: int,
) -> MockDrive:
    """Create a new MockDrive with status=draft."""
    bp = None
    if payload.blueprint_id is not None:
        bp = _validate_and_attach_blueprint(
            db=db,
            company_name=payload.company_name,
            target_role=payload.target_role,
            blueprint_id=payload.blueprint_id,
        )

    # Normalize selected_rounds to Dict[str, bool]
    selected_rounds: dict = {}
    raw_sr = payload.selected_rounds
    if isinstance(raw_sr, dict):
        selected_rounds = {k: bool(v) for k, v in raw_sr.items() if k in VALID_ROUNDS}
    elif isinstance(raw_sr, list):
        selected_rounds = {r: True for r in raw_sr if r in VALID_ROUNDS}

    # If payload provided explicit rounds, they are the single source of truth.
    # Only fall back to blueprint rounds if no explicit rounds were selected.
    if bp and not any(selected_rounds.values()):
        bp_rounds = (bp.blueprint_data or {}).get("rounds", [])
        for r in bp_rounds:
            rtype = r.get("round_type")
            if rtype in VALID_ROUNDS:
                selected_rounds[rtype] = True

    drive_snapshot = snapshot_company_blueprint(bp) if bp else None
    # With an attached blueprint the pinned snapshot is the sole authority:
    # round_configurations is derived server-side and client input is ignored.
    # Blueprint-less drives keep the legacy client-supplied behavior.
    if bp is not None:
        round_configurations = _round_configurations_from_snapshot(
            drive_snapshot, selected_rounds
        )
    else:
        round_configurations = payload.round_configurations

    drive = MockDrive(
        company_name=payload.company_name,
        target_role=payload.target_role,
        description=payload.description,
        status="draft",
        minimum_cgpa=payload.minimum_cgpa,
        maximum_backlogs=payload.maximum_backlogs,
        eligible_branches=payload.eligible_branches,
        selected_rounds=selected_rounds,
        round_configurations=round_configurations,
        blueprint_id=bp.id if bp else None,
        blueprint_version=bp.version if bp else None,
        blueprint_snapshot=drive_snapshot,
        created_by_id=created_by_id,
    )
    db.add(drive)
    db.commit()
    db.refresh(drive)
    return drive


def list_mock_drives(
    db: Session,
    status_filter: Optional[str] = None,
) -> List[MockDrive]:
    """Return all mock drives, optionally filtered by status."""
    query = db.query(MockDrive).order_by(MockDrive.created_at.desc())
    if status_filter and status_filter != "all":
        query = query.filter(MockDrive.status == status_filter)
    return query.all()


def get_mock_drive(db: Session, mock_drive_id: int) -> MockDrive:
    """Return a single MockDrive by id, or raise 404."""
    return _get_or_404(db, mock_drive_id)


def update_mock_drive(
    db: Session,
    mock_drive_id: int,
    payload: MockDriveUpdate,
) -> MockDrive:
    """Update a DRAFT MockDrive. Raises 404 or 422 on invalid state."""
    drive = _get_or_404(db, mock_drive_id)
    _assert_draft(drive, action="edit")

    update_data = payload.model_dump(exclude_unset=True)

    new_company = update_data.get("company_name", drive.company_name)
    new_role = update_data.get("target_role", drive.target_role)

    identity_changed = (
        new_company.strip().lower() != drive.company_name.strip().lower()
        or new_role.strip().lower() != drive.target_role.strip().lower()
    )
    blueprint_changed = (
        "blueprint_id" in update_data
        and update_data.get("blueprint_id") != drive.blueprint_id
    )
    if identity_changed or blueprint_changed:
        target_bp_id = update_data.get("blueprint_id", drive.blueprint_id)
        if target_bp_id is not None:
            bp = _validate_and_attach_blueprint(
                db=db,
                company_name=new_company,
                target_role=new_role,
                blueprint_id=target_bp_id,
            )
            drive.blueprint_id = bp.id
            drive.blueprint_version = bp.version
            drive.blueprint_snapshot = snapshot_company_blueprint(bp)
        else:
            drive.blueprint_id = None
            drive.blueprint_version = None
            drive.blueprint_snapshot = None

    # Update selected_rounds if provided, normalizing to Dict[str, bool]
    if "selected_rounds" in update_data and update_data["selected_rounds"] is not None:
        raw_sr = update_data["selected_rounds"]
        if isinstance(raw_sr, dict):
            drive.selected_rounds = {k: bool(v) for k, v in raw_sr.items() if k in VALID_ROUNDS}
        elif isinstance(raw_sr, list):
            drive.selected_rounds = {r: True for r in raw_sr if r in VALID_ROUNDS}

    for field, value in update_data.items():
        if field in ("blueprint_id", "selected_rounds"):
            continue
        # With an attached blueprint the pinned snapshot is the sole authority:
        # round_configurations is derived server-side and client input is ignored.
        # Blueprint-less drives keep the legacy client-supplied behavior.
        if field == "round_configurations" and drive.blueprint_id is not None:
            continue
        setattr(drive, field, value)

    if drive.blueprint_id is not None and drive.blueprint_snapshot is not None:
        drive.round_configurations = _round_configurations_from_snapshot(
            drive.blueprint_snapshot, drive.selected_rounds
        )

    db.commit()
    db.refresh(drive)
    return drive



def delete_mock_drive(db: Session, mock_drive_id: int) -> None:
    """Delete a DRAFT MockDrive. Raises 404 or 422 on invalid state."""
    drive = _get_or_404(db, mock_drive_id)
    _assert_draft(drive, action="delete")

    db.delete(drive)
    db.commit()


# ── Phase 3A: Publish ─────────────────────────────────────────────────

def publish_mock_drive(db: Session, mock_drive_id: int) -> MockDrive:
    """Transition a DRAFT MockDrive to PUBLISHED after validation.

    Validation rules:
    - Must be in draft status.
    - company_name and target_role must be non-empty.
    - If blueprint is linked, must exist, be approved, and match company + role.
    - At least one round must be selected (enabled = True).
    - minimum_cgpa must be in [0, 10].
    - maximum_backlogs must be >= 0.
    """
    drive = _get_or_404(db, mock_drive_id)
    _assert_draft(drive, action="publish")

    if drive.blueprint_id:
        _validate_and_attach_blueprint(
            db=db,
            company_name=drive.company_name,
            target_role=drive.target_role,
            blueprint_id=drive.blueprint_id,
        )
        blueprint_snapshot = get_drive_blueprint_snapshot(db, drive)

        # Preserve existing explicit selected rounds if present.
        # Only fall back to blueprint rounds if the drive has NO explicit rounds.
        raw_sr = drive.selected_rounds
        has_explicit = False
        if isinstance(raw_sr, dict) and any(raw_sr.values()):
            has_explicit = True
        elif isinstance(raw_sr, list) and len(raw_sr) > 0:
            has_explicit = True
            drive.selected_rounds = {r: True for r in raw_sr if r in VALID_ROUNDS}

        if not has_explicit:
            bp_rounds = (blueprint_snapshot or {}).get("blueprint_data", {}).get("rounds", [])
            drive.selected_rounds = {
                r.get("round_type"): True for r in bp_rounds if r.get("round_type") in VALID_ROUNDS
            }

    # Field completeness validation
    errors = []
    if not (drive.company_name or "").strip():
        errors.append("company_name is required before publishing.")
    if not (drive.target_role or "").strip():
        errors.append("target_role is required before publishing.")
    if not isinstance(drive.selected_rounds, dict) or not any(
        drive.selected_rounds.values()
    ):
        errors.append("At least one assessment round must be selected before publishing.")
    if not (0.0 <= (drive.minimum_cgpa or 0.0) <= 10.0):
        errors.append("minimum_cgpa must be between 0 and 10.")
    if (drive.maximum_backlogs or 0) < 0:
        errors.append("maximum_backlogs must be >= 0.")
    # Validate round keys
    unknown = set((drive.selected_rounds or {}).keys()) - set(VALID_ROUNDS)
    if unknown:
        errors.append(f"Unknown round(s) in selected_rounds: {unknown}")

    # LLM-provenance guard: any enabled round the seeded bank cannot satisfy
    # (interview rounds always; aptitude/coding rounds with role-specific topics)
    # requires a complete, validated pre-generated question pool before publish.
    if drive.blueprint_id:
        from app.services.question_pool_generation_service import (
            question_pool_generation_service,
        )

        errors += question_pool_generation_service.publish_blocking_errors(db, drive)

    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"message": "Mock drive cannot be published.", "errors": errors},
        )

    drive.status = "published"
    db.commit()
    db.refresh(drive)
    return drive


# ── Phase 3B: Student eligibility list ───────────────────────────────

def _student_is_eligible(drive: MockDrive, profile: StudentProfile) -> bool:
    """Return True if the student meets the drive's eligibility criteria."""
    cgpa = float(profile.cgpa or 0.0)
    backlogs = int(profile.backlogs_count or 0)
    branch = (profile.department or "").strip()

    if cgpa < drive.minimum_cgpa:
        return False
    if backlogs > drive.maximum_backlogs:
        return False
    # If eligible_branches is configured (non-empty list), the student must be in it.
    branches = drive.eligible_branches or []
    if branches and branch not in branches:
        return False
    return True


def list_eligible_mock_drives(
    db: Session,
    student_id: int,
) -> List[MockDrive]:
    """Return PUBLISHED MockDrives the student is eligible for and has not completed.

    Completion is tracked per candidate on their ``AssessmentContext`` (the
    drive's global status intentionally stays ``published`` while candidates
    attempt it), so drives the calling student has already completed are hidden
    from their list. In-progress and not-yet-started drives remain visible. The
    completed attempt stays reachable through the result endpoint.
    """
    profile = (
        db.query(StudentProfile)
        .filter(StudentProfile.user_id == student_id)
        .first()
    )
    if profile is None:
        return []

    published = (
        db.query(MockDrive)
        .filter(MockDrive.status == "published")
        .order_by(MockDrive.created_at.desc())
        .all()
    )
    eligible = [d for d in published if _student_is_eligible(d, profile)]
    if not eligible:
        return []

    # Single query (no N+1) for the candidate's completed drives among the
    # eligible set; SQLite caps variables but eligible sets are small.
    completed_ids = {
        row[0]
        for row in db.query(AssessmentContext.mock_drive_id)
        .filter(
            AssessmentContext.student_id == student_id,
            AssessmentContext.mock_drive_id.in_([d.id for d in eligible]),
            AssessmentContext.status == "completed",
        )
        .all()
        if row[0] is not None
    }
    return [d for d in eligible if d.id not in completed_ids]


# ── Phase 3B/3C: Start a Mock Drive session ───────────────────────────

# Mapping from MockDrive round keys to frontend route paths
ROUND_ROUTES = {
    "aptitude": "/aptitude",
    "coding": "/coding",
    "technical_interview": "/interview",
    "hr_interview": "/interview",
}

# Mapping from MockDrive round keys to AssessmentRound.round_type values
# (the DB CHECK constraint only allows: aptitude, coding, interview)
ROUND_TYPE_MAP = {
    "aptitude": "aptitude",
    "coding": "coding",
    "technical_interview": "interview",
    "hr_interview": "interview",
}

# Ordered round sequence (the order in which rounds should be attempted)
ROUND_ORDER = ["aptitude", "coding", "technical_interview", "hr_interview"]


def _apply_round_key(assessment_round: AssessmentRound, round_key: str) -> None:
    """Persist the canonical MockDrive round key on an AssessmentRound.

    The DB CHECK constraint only allows ``round_type`` in
    ``("aptitude", "coding", "interview")``, so both interview rounds are
    stored with ``round_type="interview"``. The canonical MockDrive key is
    kept in the existing nullable ``practice_type`` column (no schema change),
    which makes each round individually identifiable after a reload and is
    already understood by ``candidate_report_router`` for interview variants.
    """
    assessment_round.practice_type = round_key


def _mock_round_key_for_round(
    assessment_round: AssessmentRound, enabled: list[str]
) -> Optional[str]:
    """Resolve an AssessmentRound back to its canonical MockDrive round key.

    Prefers the persisted canonical key (``practice_type``) so a technical
    interview and an HR interview (which share ``round_type="interview"``) stay
    distinct across reloads. Falls back to the legacy ``round_type`` reverse
    map for rounds created before the canonical key was persisted
    (``practice_type`` is NULL), preserving backward compatibility.
    """
    stored = getattr(assessment_round, "practice_type", None)
    if stored and stored in enabled:
        return stored
    return next(
        (k for k in enabled if ROUND_TYPE_MAP.get(k) == assessment_round.round_type),
        None,
    )


def _enabled_rounds_in_order(drive: MockDrive) -> list[str]:
    """Return the drive's enabled rounds in canonical or blueprint-defined order.

    1. The draft's saved rounds configuration is the single source of truth.
    2. If an approved blueprint is attached, blueprint-derived round sequence is authoritative.
       Any enabled rounds present in the blueprint follow the blueprint's order, followed by
       any additional enabled rounds in canonical order.
    3. If no blueprint is attached, enabled rounds follow canonical ROUND_ORDER.
    4. When rounds is actually missing/null/empty (legacy drive), fall back to canonical ROUND_ORDER
       (or blueprint rounds if blueprint attached).
    """
    sr = drive.selected_rounds
    enabled_set = set()
    if isinstance(sr, dict):
        enabled_set = {r for r, on in sr.items() if on and r in VALID_ROUNDS}
    elif isinstance(sr, list):
        enabled_set = {r for r in sr if r in VALID_ROUNDS}

    if drive.blueprint_id and (drive.blueprint_snapshot or drive.blueprint):
        blueprint_data = (
            (drive.blueprint_snapshot or {}).get("blueprint_data")
            if drive.blueprint_snapshot
            else drive.blueprint.blueprint_data
        )
        bp_rounds = (blueprint_data or {}).get("rounds", [])
        if bp_rounds:
            sorted_bp_rounds = sorted(bp_rounds, key=lambda x: x.get("round_order", 99))
            bp_order = [
                r.get("round_type") for r in sorted_bp_rounds
                if r.get("round_type") in VALID_ROUNDS
            ]
            if bp_order:
                if enabled_set:
                    bp_enabled = [r for r in bp_order if r in enabled_set]
                    extra_enabled = [r for r in ROUND_ORDER if r in enabled_set and r not in bp_enabled]
                    return bp_enabled + extra_enabled
                return bp_order

    if enabled_set:
        return [r for r in ROUND_ORDER if r in enabled_set]

    # Legacy fallback: only when rounds is missing/null/empty
    return list(ROUND_ORDER)


def _get_completed_drive_context(
    db: Session, mock_drive_id: int, student_id: int
) -> Optional[AssessmentContext]:
    """Return this student's latest completed attempt for the drive, if any."""
    return (
        db.query(AssessmentContext)
        .filter(
            AssessmentContext.mock_drive_id == mock_drive_id,
            AssessmentContext.student_id == student_id,
            AssessmentContext.status == "completed",
        )
        .order_by(AssessmentContext.id.desc())
        .first()
    )


def _completed_drive_response(
    drive: MockDrive, completed_ctx: Optional[AssessmentContext]
) -> dict:
    """Graceful 'already completed' payload for a candidate's finished attempt."""
    return {
        "session_id": None,
        "context_id": completed_ctx.id if completed_ctx else None,
        "mock_drive_id": drive.id,
        "company_name": drive.company_name,
        "target_role": drive.target_role,
        "blueprint_id": drive.blueprint_id,
        "blueprint_version": drive.blueprint_version,
        "enabled_rounds": _enabled_rounds_in_order(drive),
        "current_round": None,
        "status": "completed",
        "already_started": True,
        "redirect_url": "/mock-drive",
    }


def start_mock_drive_session(
    db: Session,
    mock_drive_id: int,
    student_id: int,
) -> dict:
    """Create an AssessmentSession linked to the MockDrive for an eligible student.

    Uses the existing AssessmentContext/Session lifecycle.
    Creates the first enabled round so the student can immediately begin.
    Returns the created session, the drive's configured rounds, and the
    first round to start.
    """
    from app.services import session_service
    drive = _get_or_404(db, mock_drive_id)

    if drive.status not in ("published", "active"):
        if drive.status == "completed":
            # Legacy drives whose global status still transitioned on completion.
            # Keep the graceful response so existing completed drives behave
            # exactly as before (backward compatibility).
            completed_ctx = _get_completed_drive_context(db, drive.id, student_id)
            _opportunistic_competency_mapping_retry(db, completed_ctx)
            return _completed_drive_response(drive, completed_ctx)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot start a mock drive with status {drive.status!r}.",
        )

    # Per-candidate attempt guard. The drive's global status intentionally stays
    # "published" while candidates attempt it, so completion is tracked per
    # candidate via their AssessmentContext (mirrors the old global-state
    # behavior for a single candidate while letting other candidates start).
    completed_ctx = _get_completed_drive_context(db, drive.id, student_id)
    if completed_ctx is not None:
        _opportunistic_competency_mapping_retry(db, completed_ctx)
        return _completed_drive_response(drive, completed_ctx)

    # Eligibility re-check
    profile = (
        db.query(StudentProfile)
        .filter(StudentProfile.user_id == student_id)
        .first()
    )
    if profile is None or not _student_is_eligible(drive, profile):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not eligible for this mock drive.",
        )

    # G3: Pool-readiness check for blueprint-backed interview rounds.
    # Before creating any session state, verify that every enabled interview
    # round has a complete, validated question pool for the pinned blueprint
    # version. This is a defense-in-depth gate complementary to the G2 publish
    # gate and G1 candidate-time fail-closed.
    if drive.blueprint_id is not None:
        from app.services.question_pool_generation_service import (
            question_pool_generation_service,
        )
        drive_snapshot = get_drive_blueprint_snapshot(db, drive)
        enabled_rounds = _enabled_rounds_in_order(drive)
        missing_pools = []
        for round_key in enabled_rounds:
            if round_key not in ("technical_interview", "hr_interview"):
                continue
            has_pool = (
                question_pool_generation_service.complete_pool_for_round(
                    db,
                    drive_snapshot.get("blueprint_id"),
                    drive_snapshot.get("blueprint_version"),
                    round_key,
                )
                is not None
            )
            if not has_pool:
                missing_pools.append(round_key)
        if missing_pools:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Cannot start mock drive: required interview question pools are missing.",
                    "missing_rounds": missing_pools,
                    "resolution": (
                        "Generate and approve the missing interview question pools in the TPO portal, "
                        "then retry starting the drive."
                    ),
                },
            )

    # Prevent duplicate active sessions for this mock drive
    existing_ctx = (
        db.query(AssessmentContext)
        .filter(
            AssessmentContext.mock_drive_id == drive.id,
            AssessmentContext.student_id == student_id,
            AssessmentContext.status == "active",
        )
        .first()
    )
    if existing_ctx is not None:
        if not existing_ctx.blueprint_snapshot and drive.blueprint_id:
            drive_snapshot = get_drive_blueprint_snapshot(db, drive)
            existing_ctx.blueprint_snapshot = snapshot_for_assessment_context(
                drive_snapshot,
                drive.selected_rounds,
                _enabled_rounds_in_order(drive),
            )
            db.commit()
        # Return the existing session so the student can resume
        existing_session = (
            db.query(AssessmentSession)
            .filter(
                AssessmentSession.context_id == existing_ctx.id,
                AssessmentSession.status == "in_progress",
            )
            .first()
        )
        if existing_session is not None:
            rounds = _enabled_rounds_in_order(drive)
            # Find current active round or default to first
            active_round = session_service.get_active_round(db, existing_session.id)
            if active_round:
                # Prefer the persisted canonical round key so a technical
                # interview and an HR interview stay distinct on reload;
                # fall back for legacy rows.
                current_round = _mock_round_key_for_round(active_round, rounds)
                if current_round is None:
                    current_round = rounds[0] if rounds else None
            else:
                current_round = rounds[0] if rounds else None
            return {
                "session_id": existing_session.id,
                "context_id": existing_ctx.id,
                "mock_drive_id": drive.id,
                "company_name": drive.company_name,
                "target_role": drive.target_role,
                "blueprint_id": drive.blueprint_id,
                "blueprint_version": drive.blueprint_version,
                "enabled_rounds": rounds,
                "current_round": current_round,
                "status": existing_session.status,
                "already_started": True,
                "redirect_url": ROUND_ROUTES.get(current_round, "/dashboard") if current_round else "/dashboard",
            }

    # Fetch the default policy for mock-drive sessions
    from app.models.assessment_context import AssessmentPolicy
    policy = db.query(AssessmentPolicy).filter(
        AssessmentPolicy.id == DEFAULT_PRACTICE_POLICY_ID
    ).first()
    if policy is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Assessment policy not configured. Contact administrator.",
        )

    # End any existing active session for this student first. A Mock-Drive-backed
    # session is finalized through the Mock Drive lifecycle (per-candidate
    # completion + competency mapping) instead of the generic session API, so
    # starting another attempt can never silently bypass the mapping step.
    # Standalone/practice sessions keep their legacy behavior.
    existing_session = session_service.get_active_session(db, student_id)
    if existing_session is not None:
        old_ctx = (
            db.query(AssessmentContext)
            .filter(AssessmentContext.id == existing_session.context_id)
            .first()
        )
        old_drive = (
            db.query(MockDrive)
            .filter(MockDrive.id == old_ctx.mock_drive_id)
            .first()
            if old_ctx is not None and old_ctx.mock_drive_id is not None
            else None
        )
        if old_ctx is not None and old_drive is not None:
            _finalize_mock_drive(db, old_drive, old_ctx, existing_session)
        else:
            session_service.complete_session(db, existing_session.id, student_id)

    # Create an AssessmentContext for this mock drive attempt
    drive_snapshot = get_drive_blueprint_snapshot(db, drive)
    enabled_rounds = _enabled_rounds_in_order(drive)
    context = AssessmentContext(
        mode=MODE_MOCK_DRIVE,
        purpose="mock_drive",
        student_id=student_id,
        created_by_id=drive.created_by_id,
        company_name=drive.company_name,
        target_role=drive.target_role,
        policy_id=policy.id,
        mock_drive_id=drive.id,
        blueprint_snapshot=snapshot_for_assessment_context(
            drive_snapshot, drive.selected_rounds, enabled_rounds
        ),
        status="active",
    )
    db.add(context)
    db.flush()  # get context.id without a full commit

    # Create the AssessmentSession linked to this context
    session = session_service.create_session(
        db=db,
        user_id=student_id,
        context_id=context.id,
    )

    # Create the first enabled round so the student can start immediately
    enabled = enabled_rounds
    first_round = enabled[0] if enabled else None
    current_round = None
    if first_round:
        # Map MockDrive round key to AssessmentRound.round_type
        # (DB CHECK constraint only allows: aptitude, coding, interview)
        round_type = ROUND_TYPE_MAP.get(first_round, "interview")
        assessment_round = session_service.create_round(
            db=db,
            session_id=session.id,
            round_type=round_type,
            practice_type=first_round,
        )
        # Persist the canonical MockDrive round key so the round stays
        # individually identifiable after a reload (technical vs HR).
        _apply_round_key(assessment_round, first_round)
        round_config = get_blueprint_round_config(drive_snapshot, first_round)
        configured_count = configured_question_count(round_config)
        if configured_count is not None:
            assessment_round.max_questions = configured_count
        db.commit()
        current_round = first_round  # Return the MockDrive key, not the mapped type

    # NOTE: the drive's global status deliberately stays "published" while
    # candidates attempt it. Per-candidate progress/completion lives on the
    # AssessmentContext/session created above, so multiple eligible candidates
    # can complete the same published drive independently.

    db.commit()
    db.refresh(context)
    db.refresh(session)

    return {
        "session_id": session.id,
        "context_id": context.id,
        "mock_drive_id": drive.id,
        "company_name": drive.company_name,
        "target_role": drive.target_role,
        "blueprint_id": drive.blueprint_id,
        "blueprint_version": drive.blueprint_version,
        "enabled_rounds": enabled,
        "current_round": current_round,
        "status": session.status,
        "already_started": False,
        "redirect_url": ROUND_ROUTES.get(current_round, "/dashboard") if current_round else "/dashboard",
    }


# ── Phase 3C-2: Round advancement + status ───────────────────────────

def _find_mock_drive_context(
    db: Session, mock_drive_id: int, student_id: int
) -> Optional[AssessmentContext]:
    """Return the active AssessmentContext for this student+drive, or None."""
    return (
        db.query(AssessmentContext)
        .filter(
            AssessmentContext.mock_drive_id == mock_drive_id,
            AssessmentContext.student_id == student_id,
            AssessmentContext.status == "active",
        )
        .first()
    )


def _opportunistic_competency_mapping_retry(
    db: Session, context: Optional[AssessmentContext]
) -> None:
    """Best-effort retry of a pending/failed competency mapping on a read path.

    Triggered when a completed Mock Drive context is observed (e.g. the
    frontend status poll). Idempotent and safe: terminal mappings are skipped,
    never-tracked (NULL) legacy contexts are left alone, and any failure is
    swallowed so read endpoints never break. No score is computed.
    """
    if context is None or context.mock_drive_id is None:
        return
    if context.competency_mapping_status not in ("pending", "failed"):
        return

    from app.services.competency_mapping_service import reprocess_competency_mapping

    session = (
        db.query(AssessmentSession)
        .filter(
            AssessmentSession.context_id == context.id,
            AssessmentSession.status == "completed",
        )
        .order_by(AssessmentSession.id.desc())
        .first()
    )
    if session is None:
        return
    try:
        reprocess_competency_mapping(db, session)
    except Exception:  # noqa: BLE001 - recovery on a read path must never fail
        db.rollback()
        logger.exception(
            "Opportunistic competency mapping retry failed for context %s.", context.id
        )


def reprocess_mock_drive_competency_mappings(
    db: Session, mock_drive_id: int
) -> dict:
    """Reprocess competency mappings for a Mock Drive's completed contexts.

    Idempotent recovery for explicit operator action. Targets completed contexts
    whose mapping is pending, failed, or not yet tracked (NULL, e.g. drives
    completed before the status column existed). Uses pinned snapshots, never
    reruns the assessment, and never changes scores.
    """
    _get_or_404(db, mock_drive_id)

    from app.services.competency_mapping_service import reprocess_competency_mapping

    contexts = (
        db.query(AssessmentContext)
        .filter(
            AssessmentContext.mock_drive_id == mock_drive_id,
            or_(
                AssessmentContext.competency_mapping_status.in_(("pending", "failed")),
                AssessmentContext.competency_mapping_status.is_(None),
            ),
        )
        .all()
    )

    result = {
        "mock_drive_id": mock_drive_id,
        "examined": 0,
        "completed": 0,
        "failed": 0,
        "skipped": 0,
        "not_applicable": 0,
    }
    for context in contexts:
        result["examined"] += 1
        session = (
            db.query(AssessmentSession)
            .filter(
                AssessmentSession.context_id == context.id,
                AssessmentSession.status == "completed",
            )
            .order_by(AssessmentSession.id.desc())
            .first()
        )
        if session is None:
            result["skipped"] += 1
            continue
        try:
            outcome = reprocess_competency_mapping(db, session)
        except Exception:  # noqa: BLE001 - report per-context, keep going
            db.rollback()
            result["failed"] += 1
            logger.exception(
                "Competency mapping reprocess failed for context %s.", context.id
            )
            continue
        outcome_status = outcome.get("status")
        if outcome_status == "completed":
            result["completed"] += 1
        elif outcome_status == "not_applicable":
            result["not_applicable"] += 1
        elif outcome_status == "failed":
            result["failed"] += 1
        else:
            result["skipped"] += 1
    return result


def get_mock_drive_status(
    db: Session, mock_drive_id: int, student_id: int,
) -> dict:
    """Return the current state of the student's mock drive attempt.

    Reports completed rounds, current active round, and whether the
    drive is in-progress or completed.
    """
    drive = _get_or_404(db, mock_drive_id)
    ctx = _find_mock_drive_context(db, mock_drive_id, student_id)

    if ctx is None:
        # No active context — check if there's a completed one
        completed_ctx = (
            db.query(AssessmentContext)
            .filter(
                AssessmentContext.mock_drive_id == mock_drive_id,
                AssessmentContext.student_id == student_id,
                AssessmentContext.status == "completed",
            )
            .first()
        )
        if completed_ctx:
            _opportunistic_competency_mapping_retry(db, completed_ctx)
            return {
                "mock_drive_id": drive.id,
                "company_name": drive.company_name,
                "target_role": drive.target_role,
                "blueprint_id": drive.blueprint_id,
                "blueprint_version": drive.blueprint_version,
                "enabled_rounds": _enabled_rounds_in_order(drive),
                "completed_rounds": _completed_rounds_for_context(db, completed_ctx, drive),
                "current_round": None,
                "status": "completed",
                "session_id": None,
                "redirect_url": None,
            }
        return {
            "mock_drive_id": drive.id,
            "company_name": drive.company_name,
            "target_role": drive.target_role,
            "blueprint_id": drive.blueprint_id,
            "blueprint_version": drive.blueprint_version,
            "enabled_rounds": _enabled_rounds_in_order(drive),
            "completed_rounds": [],
            "current_round": None,
            "status": "not_started",
            "session_id": None,
            "redirect_url": None,
        }

    session = (
        db.query(AssessmentSession)
        .filter(
            AssessmentSession.context_id == ctx.id,
            AssessmentSession.status == "in_progress",
        )
        .first()
    )

    if session is None:
        # Context exists but session completed/expired
        _opportunistic_competency_mapping_retry(db, ctx)
        return {
            "mock_drive_id": drive.id,
            "company_name": drive.company_name,
            "target_role": drive.target_role,
            "blueprint_id": drive.blueprint_id,
            "blueprint_version": drive.blueprint_version,
            "enabled_rounds": _enabled_rounds_in_order(drive),
            "completed_rounds": _completed_rounds_for_context(db, ctx, drive),
            "current_round": None,
            "status": "completed",
            "session_id": None,
            "redirect_url": None,
        }

    enabled = _enabled_rounds_in_order(drive)
    completed = _completed_rounds_for_context(db, ctx, drive)

    # Find the active round directly (avoid session_service.get_active_round
    # which does _expire_stale_rounds + for_update, causing locks in this read path)
    active_round = (
        db.query(AssessmentRound)
        .filter(
            AssessmentRound.session_id == session.id,
            AssessmentRound.status == "active",
        )
        .order_by(AssessmentRound.id.desc())
        .first()
    )

    # Map the active round_type back to MockDrive key
    current_round = None
    if active_round:
        current_round = _mock_round_key_for_round(active_round, enabled)

    # If no active round, find the next uncompleted one
    if current_round is None:
        remaining = [r for r in enabled if r not in completed]
        if remaining:
            current_round = remaining[0]
        else:
            # All rounds completed — mark drive complete
            _finalize_mock_drive(db, drive, ctx, session)
            return {
                "mock_drive_id": drive.id,
                "company_name": drive.company_name,
                "target_role": drive.target_role,
                "blueprint_id": drive.blueprint_id,
                "blueprint_version": drive.blueprint_version,
                "enabled_rounds": enabled,
                "completed_rounds": completed,
                "current_round": None,
                "status": "completed",
                "session_id": session.id,
                "redirect_url": "/mock-drive",
            }

    return {
        "mock_drive_id": drive.id,
        "company_name": drive.company_name,
        "target_role": drive.target_role,
        "blueprint_id": drive.blueprint_id,
        "blueprint_version": drive.blueprint_version,
        "enabled_rounds": enabled,
        "completed_rounds": completed,
        "current_round": current_round,
        "status": "in_progress",
        "session_id": session.id,
        "redirect_url": ROUND_ROUTES.get(current_round, "/dashboard"),
    }



def _completed_rounds_for_context(
    db: Session, ctx: AssessmentContext, drive: MockDrive,
) -> list[str]:
    """Return MockDrive round keys that have a completed or expired AssessmentRound.

    Both "completed" and "expired" rounds are considered finished for mock drive
    progression purposes. Expired rounds are those that timed out and were
    finalized with TIME_EXPIRED.
    """
    enabled = _enabled_rounds_in_order(drive)
    sessions = (
        db.query(AssessmentSession)
        .filter(AssessmentSession.context_id == ctx.id)
        .all()
    )
    if not sessions:
        return []
    session_ids = [s.id for s in sessions]
    finished_rounds = (
        db.query(AssessmentRound)
        .filter(
            AssessmentRound.session_id.in_(session_ids),
            AssessmentRound.status.in_(("completed", "expired")),
        )
        .all()
    )
    # Map each finished AssessmentRound back to its MockDrive key. The
    # canonical key is preferred so a finished technical interview does not
    # also mark the HR interview complete (both share round_type "interview").
    result = []
    for cr in finished_rounds:
        key = _mock_round_key_for_round(cr, enabled)
        if key is not None and key not in result:
            result.append(key)
    return result


def _assert_manual_round_completion(
    db: Session, active_round: AssessmentRound
) -> None:
    """Reject premature manual completion of the active round.

    The candidate-facing "Complete Round" action bypasses the round engine's
    own finish handler, so the required preconditions are re-checked here,
    server-side. Only the blueprint-backed aptitude round has an explicit work
    requirement (at least one recorded attempt — see POST /aptitude/finish,
    which refuses to finish a blueprint aptitude round with no attempts).
    Coding and interview explicitly allow finishing without submissions/turns,
    so no additional requirement is imposed for them (legitimate skip/submit
    behavior is preserved).
    """
    if active_round.round_type != "aptitude":
        return

    snapshot, blueprint_round = get_session_blueprint_round_config(
        db, active_round.session_id, "aptitude"
    )
    if not snapshot or not blueprint_round:
        return

    # Count across the whole session, not just the active round: a blueprint
    # aptitude round can be re-created (timeout + resume, drive re-entry) after
    # answers were already recorded on a sibling aptitude round, leaving the
    # active round with no attempts while the candidate's work is preserved.
    # Only a session with no aptitude attempts at all is genuinely incomplete.
    attempts = (
        db.query(func.count(AptitudeAttempt.id))
        .join(AssessmentRound, AssessmentRound.id == AptitudeAttempt.round_id)
        .filter(
            AssessmentRound.session_id == active_round.session_id,
            AssessmentRound.round_type == "aptitude",
        )
        .scalar()
    ) or 0
    if attempts == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Cannot complete this aptitude round because no aptitude "
                "questions were completed. Answer at least one question "
                "before completing the round."
            ),
        )


def advance_mock_drive_round(
    db: Session, mock_drive_id: int, student_id: int,
) -> dict:
    """Complete the current round and activate the next enabled round.

    If this was the final round, mark the mock drive as completed.
    """
    from app.services import session_service
    drive = _get_or_404(db, mock_drive_id)
    ctx = _find_mock_drive_context(db, mock_drive_id, student_id)
    if ctx is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active mock drive session found. Start the drive first.",
        )

    session = (
        db.query(AssessmentSession)
        .filter(
            AssessmentSession.context_id == ctx.id,
            AssessmentSession.status == "in_progress",
        )
        .first()
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mock drive session is not in progress.",
        )

    enabled = _enabled_rounds_in_order(drive)
    completed = _completed_rounds_for_context(db, ctx, drive)

    # Server-authoritative expiry (Phase 4C Part 3): the persisted round/session
    # deadlines are the sole authority; no client-supplied timer is consulted.
    # An overdue round must not be completed, advanced, or — critically —
    # silently re-created with a fresh deadline by this manual "Complete Round"
    # action. This runs before any completion/advance decision.
    now = datetime.utcnow()
    session_expired = (
        session.expires_at is not None and session.expires_at <= now
    )
    latest_round = (
        db.query(AssessmentRound)
        .filter(AssessmentRound.session_id == session.id)
        .order_by(AssessmentRound.id.desc())
        .first()
    )
    round_expired = (
        latest_round is not None
        and latest_round.status in ("active", "expired")
        and latest_round.expires_at is not None
        and latest_round.expires_at <= now
    )
    already_expired = latest_round is not None and latest_round.status == "expired"
    if session_expired or round_expired or already_expired:
        if latest_round is not None and latest_round.status == "active":
            # Get the round key for proper timeout handling
            round_key = _mock_round_key_for_round(latest_round, enabled)
            # Finalize the expired round with TIME_EXPIRED and advance
            _finalize_expired_round(db, session, latest_round, round_key)
            # Re-read the updated state
            db.expire_all()
            session = (
                db.query(AssessmentSession)
                .filter(
                    AssessmentSession.context_id == ctx.id,
                    AssessmentSession.status == "in_progress",
                )
                .first()
            )
            if session is None:
                # Session was finalized
                raise HTTPException(
                    status_code=status.HTTP_410_GONE,
                    detail="This mock drive has been completed due to timeout."
                )
        elif latest_round is not None and latest_round.status == "expired":
            # Round is already expired but not yet finalized - advance to next round directly
            # without calling _finalize_expired_round again to avoid infinite recursion
            enabled = _enabled_rounds_in_order(drive)
            completed = _completed_rounds_for_context(db, ctx, drive)
            remaining = [r for r in enabled if r not in completed]
            if remaining:
                next_round_key = remaining[0]
                round_type = ROUND_TYPE_MAP.get(next_round_key, "interview")

                # Check if a round of this type already exists and is active/pending.
                existing = (
                    db.query(AssessmentRound)
                    .filter(
                        AssessmentRound.session_id == session.id,
                        AssessmentRound.status.in_(["active", "pending"]),
                    )
                    .filter(
                        (AssessmentRound.practice_type == next_round_key)
                        | (
                            (AssessmentRound.practice_type.is_(None))
                            & (AssessmentRound.round_type == round_type)
                        )
                    )
                    .first()
                )
                if existing is None:
                    existing = session_service.create_round(
                        db=db, session_id=session.id, round_type=round_type,
                        practice_type=next_round_key,
                    )
                # Persist/refresh the canonical round key on the activated round.
                _apply_round_key(existing, next_round_key)
                round_config = get_blueprint_round_config(ctx.blueprint_snapshot, next_round_key)
                configured_count = configured_question_count(round_config)
                if existing is not None and configured_count is not None:
                    existing.max_questions = configured_count
                db.commit()
            else:
                # No rounds remain — finalize the mock drive so the candidate's
                # attempt reaches a terminal, completed state. Without this the
                # session/context would stay "in_progress"/"active" forever when
                # the final round times out.
                _finalize_mock_drive(db, drive, ctx, session)
            # Mark session as expired if needed
            if session_expired and session.status == "in_progress":
                session.status = "expired"
                session.completed_at = now
                db.commit()
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                "This assessment round has expired and has been finalized. "
                "The mock drive has advanced to the next round or completed."
            ),
        )

    # Complete the current active round — direct query to avoid
    # session_service.get_active_round which uses for_update (causes locks)
    active_round = (
        db.query(AssessmentRound)
        .filter(
            AssessmentRound.session_id == session.id,
            AssessmentRound.status == "active",
        )
        .order_by(AssessmentRound.id.desc())
        .first()
    )
    if active_round is not None:
        _assert_manual_round_completion(db, active_round)
        active_round.status = "completed"
        active_round.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(active_round)
        # Add to completed list (canonical key, so a finished technical
        # interview does not also mark the HR interview complete)
        active_key = _mock_round_key_for_round(active_round, enabled)
        if active_key is not None and active_key not in completed:
            completed.append(active_key)

    # Find next uncompleted round
    remaining = [r for r in enabled if r not in completed]

    if not remaining:
        # All rounds completed — finalize the mock drive
        _finalize_mock_drive(db, drive, ctx, session)
        return {
            "mock_drive_id": drive.id,
            "company_name": drive.company_name,
            "target_role": drive.target_role,
            "blueprint_id": drive.blueprint_id,
            "blueprint_version": drive.blueprint_version,
            "enabled_rounds": enabled,
            "completed_rounds": completed,
            "current_round": None,
            "status": "completed",
            "session_id": session.id,
            "redirect_url": "/mock-drive",
        }

    # Create/activate the next round
    next_round_key = remaining[0]
    round_type = ROUND_TYPE_MAP.get(next_round_key, "interview")

    # Check if a round of this type already exists and is active/pending.
    # Match on the persisted canonical key, so a pending HR interview is never
    # reused as the technical interview (both share round_type "interview").
    # Legacy rows (practice_type NULL) keep the round_type match.
    existing = (
        db.query(AssessmentRound)
        .filter(
            AssessmentRound.session_id == session.id,
            AssessmentRound.status.in_(["active", "pending"]),
        )
        .filter(
            (AssessmentRound.practice_type == next_round_key)
            | (
                AssessmentRound.practice_type.is_(None)
                & (AssessmentRound.round_type == round_type)
            )
        )
        .first()
    )
    if existing is None:
        existing = session_service.create_round(
            db=db, session_id=session.id, round_type=round_type,
            practice_type=next_round_key,
        )
    # Persist/refresh the canonical round key on the activated round.
    _apply_round_key(existing, next_round_key)
    round_config = get_blueprint_round_config(ctx.blueprint_snapshot, next_round_key)
    configured_count = configured_question_count(round_config)
    if existing is not None and configured_count is not None:
        existing.max_questions = configured_count
    db.commit()

    return {
        "mock_drive_id": drive.id,
        "company_name": drive.company_name,
        "target_role": drive.target_role,
        "blueprint_id": drive.blueprint_id,
        "blueprint_version": drive.blueprint_version,
        "enabled_rounds": enabled,
        "completed_rounds": completed,
        "current_round": next_round_key,
        "status": "in_progress",
        "session_id": session.id,
        "redirect_url": ROUND_ROUTES.get(next_round_key, "/dashboard"),
    }



# ── Phase 3C-3: Hook helper — called by engine completion handlers ─────

def try_advance_mock_drive(db: Session, session_id: int) -> Optional[dict]:
    """If this session belongs to a mock drive, advance to the next round.

    Returns the advance result dict if a mock drive was advanced/completed,
    or None if the session is not part of a mock drive.

    Designed to be called from the end of each engine's completion handler
    without breaking standalone (non-mock-drive) flows.
    """
    from app.models.assessment import AssessmentSession, AssessmentRound
    from app.models.assessment_context import AssessmentContext

    session = db.query(AssessmentSession).filter(
        AssessmentSession.id == session_id
    ).first()
    if session is None or session.context_id is None:
        return None

    ctx = db.query(AssessmentContext).filter(
        AssessmentContext.id == session.context_id
    ).first()
    if ctx is None or ctx.mock_drive_id is None:
        return None

    # This session is part of a mock drive — advance it
    try:
        return advance_mock_drive_round(
            db=db,
            mock_drive_id=ctx.mock_drive_id,
            student_id=session.user_id,
        )
    except HTTPException:
        # If the drive is already completed or context gone, ignore gracefully
        return None


# ── G5: Timeout finalization ─────────────────────────────────────────────

def _finalize_expired_round(
    db: Session,
    session: AssessmentSession,
    expired_round: AssessmentRound,
    round_key: str,
) -> bool:
    """Finalize an expired round with TIME_EXPIRED completion reason.

    Scores available evidence, marks the round as expired with TIME_EXPIRED
    completion reason, and attempts to advance the mock drive to the next
    round. Returns True if the mock drive was advanced or finalized.

    Idempotent: safe to call multiple times for the same round.
    """
    # Only process if the round is still active (not already expired/completed)
    if expired_round.status not in ("active",):
        return False

    now = datetime.utcnow()

    # Mark the round as expired with TIME_EXPIRED completion reason
    expired_round.status = "expired"
    expired_round.completed_at = now

    # Set completion_reason = TIME_EXPIRED on the interview session if this is an interview round
    if round_key in ("technical_interview", "hr_interview"):
        interview_session = (
            db.query(InterviewSession)
            .filter(
                InterviewSession.session_id == session.id,
                InterviewSession.phase == ("HR" if round_key == "hr_interview" else "TECHNICAL"),
            )
            .first()
        )
        if interview_session and interview_session.completion_reason is None:
            interview_session.completion_reason = "TIME_EXPIRED"
            interview_session.completed_at = now
            interview_session.status = "COMPLETED"

    # Commit the round expiry
    db.commit()
    db.refresh(expired_round)

    # Attempt to advance the mock drive
    drive = (
        db.query(MockDrive)
        .filter(MockDrive.id == session.context.mock_drive_id)
        .first()
    )
    ctx = session.context

    if drive is None or ctx is None:
        return False

    # Try to advance the mock drive - this will create the next round or finalize
    try:
        result = advance_mock_drive_round(
            db=db,
            mock_drive_id=drive.id,
            student_id=session.user_id,
        )
        return True
    except HTTPException:
        # If advance fails (e.g., already completed), that's fine
        return False


def _finalize_mock_drive(
    db: Session,
    drive: MockDrive,
    ctx: AssessmentContext,
    session: AssessmentSession,
) -> None:
    """Mark the mock drive session/context as completed."""
    # Complete the session directly (avoid session_service.complete_session
    # which uses for_update, causing locks in this path)
    if session.status != "completed":
        session.status = "completed"
        session.completed_at = datetime.utcnow()
    # Mark any active rounds as completed
    db.query(AssessmentRound).filter(
        AssessmentRound.session_id == session.id,
        AssessmentRound.status == "active",
    ).update({"status": "completed", "completed_at": datetime.utcnow()})
    # Mark context completed
    ctx.status = "completed"
    ctx.completed_at = datetime.utcnow()
    # Phase 4C reliability: mark the competency mapping "pending" before the
    # completion commit, so a crash before the mapping attempt leaves a
    # detectable, recoverable state. Never downgrade a terminal mapping.
    if ctx.competency_mapping_status not in ("completed", "not_applicable"):
        ctx.competency_mapping_status = "pending"
    # NOTE: the drive's global status is NOT changed here. Completion is a
    # per-candidate concern (ctx/session above); flipping the shared drive to
    # "completed" would hide it from other eligible candidates and block their
    # attempts.
    db.commit()
    db.refresh(ctx)
    db.refresh(drive)

    # Phase 4C Part 4: additive evidence→competency mapping for the completed
    # assessment. Imported locally to avoid import cycles. Best-effort and
    # idempotent (see ``finalize_session_competency_mapping``): it runs after
    # the completion commit, never blocks completion, and repeated
    # finalization creates no duplicate mappings. No score is computed.
    from app.services.competency_mapping_service import (
        finalize_session_competency_mapping,
    )

    finalize_session_competency_mapping(db, session)


# ── G6: Consolidated Mock Drive Result ──────────────────────────────────
# Builds a consolidated result view aggregating per-round data for a candidate.

def get_mock_drive_result(
    db: Session, mock_drive_id: int, student_id: int,
) -> Optional[dict]:
    """Build a consolidated result view for a candidate's Mock Drive attempt.

    Returns None if no context/session exists for this student+drive.
    """
    from app.modules.aptitude.services.aptitude_service import (
        get_latest_completed_aptitude_result,
    )
    from app.modules.coding.routers.coding_router import get_results as coding_get_results
    from app.modules.interview.routers.interview_router import get_report
    from app.models.interview import InterviewSession

    drive = _get_or_404(db, mock_drive_id)

    # Find the candidate's context (active or completed)
    ctx = (
        db.query(AssessmentContext)
        .filter(
            AssessmentContext.mock_drive_id == mock_drive_id,
            AssessmentContext.student_id == student_id,
            AssessmentContext.status.in_(("active", "completed")),
        )
        .order_by(AssessmentContext.id.desc())
        .first()
    )

    # If no context exists for this student, they haven't started the drive
    if ctx is None:
        return None

    # Find the session (active or completed)
    session = (
        db.query(AssessmentSession)
        .filter(
            AssessmentSession.context_id == ctx.id,
            AssessmentSession.status.in_(("in_progress", "completed", "expired")),
        )
        .order_by(AssessmentSession.id.desc())
        .first()
    )
    if session is None:
        return None

    # Get enabled rounds in order
    enabled = _enabled_rounds_in_order(drive)

    # Get completed/expired rounds
    finished_rounds = _completed_rounds_for_context(db, ctx, drive)

    # Build per-round summaries
    rounds_summary = []
    overall_score_sum = 0.0
    round_count = 0

    # Fetch per-round data for each enabled round
    for round_key in enabled:
        round_type = ROUND_TYPE_MAP.get(round_key)
        if not round_type:
            continue

        round_summary = {
            "round_type": round_key,
            "status": "not_started",
            "score": None,
            "max_score": None,
            "completion_reason": None,
            "completed_at": None,
            "details": None,
        }

        if round_key in finished_rounds:
            round_summary["status"] = "completed"

            # Get the specific round
            round_obj = (
                db.query(AssessmentRound)
                .join(AssessmentSession, AssessmentRound.session_id == AssessmentSession.id)
                .filter(
                    AssessmentSession.context_id == ctx.id,
                    AssessmentRound.round_type == round_type,
                    AssessmentRound.status.in_(("completed", "expired")),
                )
                .order_by(AssessmentRound.id.desc())
                .first()
            )

            if round_obj:
                round_summary["completed_at"] = round_obj.completed_at

                if round_key in ("technical_interview", "hr_interview"):
                    # Interview round
                    interview = (
                        db.query(InterviewSession)
                        .filter(
                            InterviewSession.session_id == round_obj.session_id,
                            InterviewSession.phase == ("HR" if round_key == "hr_interview" else "TECHNICAL"),
                        )
                        .first()
                    )
                    if interview:
                        round_summary["completion_reason"] = interview.completion_reason
                        # Interview score is computed from turns
                        try:
                            # Compute interview score directly from turns
                            from app.modules.interview.routers.interview_router import _get_interview_for_user
                            from app.models.interview import InterviewTurn
                            turns = db.query(InterviewTurn).filter(
                                InterviewTurn.interview_id == interview.id
                            ).order_by(InterviewTurn.id).all()
                            main_turns = [t for t in turns if not t.is_followup]
                            if main_turns:
                                final_scores = [t.final_score for t in turns if not t.is_followup and t.final_score is not None]
                                if final_scores:
                                    round_summary["score"] = round(sum(final_scores) / len(final_scores), 2)
                                else:
                                    round_summary["score"] = 0.0
                            else:
                                round_summary["score"] = 0.0
                            round_summary["max_score"] = 100.0
                        except:
                            pass

                elif round_key == "aptitude":
                    # Aptitude round
                    result = get_latest_completed_aptitude_result(db=db, user_id=student_id)
                    if result:
                        round_summary["score"] = result.get("score")
                        round_summary["max_score"] = 100.0
                        round_summary["details"] = result

                elif round_key == "coding":
                    # Coding round
                    try:
                        # Get the session for this context
                        session_obj = (
                            db.query(AssessmentSession)
                            .filter(AssessmentSession.context_id == ctx.id)
                            .order_by(AssessmentSession.id.desc())
                            .first()
                        )
                        if session_obj:
                            # For now, compute from round score
                            if round_obj.score is not None:
                                round_summary["score"] = round_obj.score
                                round_summary["max_score"] = 100.0
                    except:
                        pass

        if round_summary["score"] is not None:
            overall_score_sum += round_summary["score"]
            round_count += 1

        rounds_summary.append(round_summary)

    # Calculate overall score (average of round scores)
    overall_score = round(overall_score_sum / round_count, 2) if round_count > 0 else None

    # Determine overall completion status
    ctx_status = "not_started"
    if ctx.status == "completed":
        ctx_status = "completed"
    elif ctx.status == "active":
        ctx_status = "in_progress"

    return {
        "mock_drive_id": drive.id,
        "company_name": drive.company_name,
        "target_role": drive.target_role,
        "blueprint_id": drive.blueprint_id,
        "blueprint_version": drive.blueprint_version,
        "status": ctx_status,
        "candidate_id": student_id,
        "session_id": session.id,
        "enabled_rounds": enabled,
        "rounds": rounds_summary,
        "overall_score": round(overall_score_sum / round_count, 2) if round_count > 0 else None,
        "total_score": round(overall_score_sum, 2) if round_count > 0 else None,
        "completed_at": ctx.completed_at,
        "completion_reason": ctx.competency_mapping_status if ctx.status == "completed" else None,
        "competency_scoring": score_session_competencies(db, session),
    }


# ── G4: Derived candidate roster ──────────────────────────────────────
# Derived entirely from authoritative AssessmentContext / AssessmentSession /
# AssessmentRound records. No duplicate assignment state is stored, and no
# eligibility, ranking, or scoring policy is invented here.

def _roster_rounds_for_session(
    db: Session, session: AssessmentSession, enabled: list[str]
) -> list[dict]:
    """One row per enabled round for a session, using only persisted state.

    Rounds may be re-created (timeout + resume / drive re-entry); the latest
    row per canonical round key wins, mirroring ``get_mock_drive_status``.
    """
    rows = (
        db.query(AssessmentRound)
        .filter(AssessmentRound.session_id == session.id)
        .all()
    )
    latest: dict[str, AssessmentRound] = {}
    for row in rows:
        key = _mock_round_key_for_round(row, enabled)
        if key is not None:
            latest[key] = row

    result: list[dict] = []
    for key in enabled:
        row = latest.get(key)
        if row is None:
            result.append({
                "round": key,
                "round_type": ROUND_TYPE_MAP.get(key, key),
                "status": "not_started",
                "deadline_passed": False,
                "score": None,
                "max_score": None,
                "completed_at": None,
            })
        else:
            finished = row.status in ("completed", "expired")
            result.append({
                "round": key,
                "round_type": row.round_type,
                "status": row.status,
                "deadline_passed": bool(
                    row.status == "expired"
                    or (row.expires_at and row.expires_at <= datetime.utcnow())
                ),
                "score": row.score if finished else None,
                "max_score": 100.0 if finished else None,
                "completed_at": row.completed_at,
            })
    return result


def get_mock_drive_roster(db: Session, mock_drive_id: int) -> dict:
    """Return the derived candidate roster for one Mock Drive (TPO/admin view).

    The roster is derived from authoritative assessment records only: each
    candidate with an ``AssessmentContext`` for this drive (active or
    completed), its latest ``AssessmentSession`` and per-round status/score.
    It does not maintain duplicate assignment state and does not invent
    eligibility, ranking, or scoring rules.
    """
    drive = _get_or_404(db, mock_drive_id)
    enabled = _enabled_rounds_in_order(drive)

    contexts = (
        db.query(AssessmentContext)
        .filter(
            AssessmentContext.mock_drive_id == mock_drive_id,
            AssessmentContext.status.in_(("active", "completed")),
        )
        .order_by(AssessmentContext.id)
        .all()
    )

    entries: list[dict] = []
    in_progress_count = 0
    completed_count = 0

    for ctx in contexts:
        session = (
            db.query(AssessmentSession)
            .filter(AssessmentSession.context_id == ctx.id)
            .order_by(AssessmentSession.id.desc())
            .first()
        )
        student = ctx.student

        if ctx.status == "completed":
            completed_count += 1
        else:
            in_progress_count += 1

        scoring = (
            score_session_competencies(db, session) if session else None
        )
        entries.append({
            "candidate_id": ctx.student_id,
            "name": getattr(student, "name", None),
            "email": getattr(student, "email", None),
            "context_id": ctx.id,
            "context_status": ctx.status,
            "session_id": session.id if session else None,
            "session_status": session.status if session else None,
            "started_at": session.started_at if session else None,
            "completed_at": ctx.completed_at,
            "overall_score": (
                session.total_score if session and scoring.get("overall_score_status") != "unavailable" else None
            ),
            "competency_mapping_status": ctx.competency_mapping_status,
            "overall_score_status": scoring.get("overall_score_status") if scoring else None,
            "evidence_coverage": scoring.get("evidence_coverage") if scoring else None,
            "assessed_competency_count": scoring.get("assessed_competency_count") if scoring else None,
            "required_competency_count": scoring.get("required_competency_count") if scoring else None,
            "missing_competencies": scoring.get("missing_competencies") if scoring else [],
            "scoring_error": scoring.get("scoring_error") if scoring else None,
            "rounds": (
                _roster_rounds_for_session(db, session, enabled) if session else []
            ),
        })

    return {
        "mock_drive_id": drive.id,
        "company_name": drive.company_name,
        "target_role": drive.target_role,
        "blueprint_id": drive.blueprint_id,
        "blueprint_version": drive.blueprint_version,
        "status": drive.status,
        "enabled_rounds": enabled,
        "total_participants": len(entries),
        "in_progress_count": in_progress_count,
        "completed_count": completed_count,
        "candidates": entries,
    }
