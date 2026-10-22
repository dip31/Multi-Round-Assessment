"""
Phase 4A: Company Historical Data & Pattern Foundation — TPO API.

Prefix: /tpo/company-data
Access: tpo + admin only

Endpoints:
  POST   /historical              — add manual historical drive record
  POST   /historical/upload       — upload file (PDF/CSV/JSON)
  GET    /historical               — list all historical records (filterable)
  GET    /historical/{id}          — get single record
  DELETE /historical/{id}          — delete record + file
  POST   /pattern/generate         — generate/recalculate pattern for company+role
  GET    /pattern                  — list all patterns
  GET    /pattern/{company}/{role} — get pattern for specific company+role
"""

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.database.db import get_db
from app.models.company_data import CompanyPattern
from app.models.user import User
from app.schemas.company_data import (
    CompanyBlueprintResponse,
    CompanyHistoricalDataCreate,
    CompanyHistoricalDataResponse,
    CompanyPatternResponse,
    GenerateBlueprintRequest,
    GeneratePatternRequest,
    ReviewBlueprintRequest,
    ReviewPatternRequest,
    RoleAssessmentGenerationRequest,
    SeedBenchmarkRequest,
    UpdateBlueprintRequest,
)
from app.services.company_data_service import (
    add_file_historical_data,
    add_manual_historical_data,
    delete_historical_data,
    generate_pattern,
    get_historical_data,
    get_pattern,
    list_available_benchmarks,
    list_historical_data,
    list_patterns,
    review_pattern,

    seed_edi5_fallback_data,
)
from app.services.company_blueprint_service import (
    approve_blueprint,
    delete_blueprint,
    generate_blueprint_from_pattern,
    get_blueprint,
    list_blueprints,
    update_blueprint,
)
from app.services.role_assessment_service import generate_role_assessment_pattern

router = APIRouter(prefix="/tpo/company-data", tags=["TPO Company Historical Data & Blueprints"])


def _require_tpo_or_admin(current_user: User) -> None:
    if current_user.role not in ("tpo", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requires TPO or admin privileges.",
        )


# ── 1. Add manual historical record ──────────────────────────────────

@router.post(
    "/historical",
    response_model=CompanyHistoricalDataResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_manual_data(
    payload: CompanyHistoricalDataCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a manually-entered past drive record for a company + role."""
    _require_tpo_or_admin(current_user)
    return add_manual_historical_data(
        db=db, payload=payload, created_by_id=current_user.id,
    )


# ── 2. Upload file ────────────────────────────────────────────────────

@router.post(
    "/historical/upload",
    response_model=CompanyHistoricalDataResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_historical_file(
    file: UploadFile = File(...),
    company_name: str = Form(..., min_length=1, max_length=200),
    target_role: str = Form(..., min_length=1, max_length=150),
    label: str = Form("Uploaded File"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a PDF, CSV, or JSON file as a historical data source for a company + role."""
    _require_tpo_or_admin(current_user)

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required.",
        )

    file_bytes = await file.read()

    return add_file_historical_data(
        db=db,
        company_name=company_name,
        target_role=target_role,
        label=label,
        file_bytes=file_bytes,
        original_filename=file.filename,
        created_by_id=current_user.id,
    )


# ── 3. List historical records ────────────────────────────────────────

@router.get("/historical", response_model=List[CompanyHistoricalDataResponse])
def list_historical(
    company_name: Optional[str] = Query(None, description="Filter by company name (partial match)"),
    target_role: Optional[str] = Query(None, description="Filter by role (partial match)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all historical data records. Optional company/role filters."""
    _require_tpo_or_admin(current_user)
    return list_historical_data(db=db, company_name=company_name, target_role=target_role)


# ── 4. Get single historical record ──────────────────────────────────

@router.get("/historical/{item_id}", response_model=CompanyHistoricalDataResponse)
def get_historical(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single historical data record by ID."""
    _require_tpo_or_admin(current_user)
    return get_historical_data(db=db, item_id=item_id)


# ── 5. Delete historical record ───────────────────────────────────────

@router.delete("/historical/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_historical(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a historical data record (and its uploaded file if any)."""
    _require_tpo_or_admin(current_user)
    delete_historical_data(db=db, item_id=item_id)


# ── 6. Generate / recalculate pattern ────────────────────────────────

@router.post("/pattern/generate", response_model=CompanyPatternResponse)
def generate_company_pattern(
    body: Optional[GeneratePatternRequest] = None,
    company_name: Optional[str] = Query(None),
    target_role: Optional[str] = Query(None),
    use_fallback: Optional[bool] = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate (or recalculate) the structured pattern for a company + role
    from all available historical data records, with optional EDI5 fallback."""
    _require_tpo_or_admin(current_user)
    c_name = body.company_name if body and body.company_name else company_name
    t_role = body.target_role if body and body.target_role else target_role
    fallback = (body.use_fallback if body and body.use_fallback is not None else use_fallback) or False
    if not c_name or not t_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="company_name and target_role are required.",
        )
    return generate_pattern(
        db=db,
        company_name=c_name,
        target_role=t_role,
        created_by_id=current_user.id,
        use_fallback=fallback,
        added_rounds=body.added_rounds if body else None,
        round_configuration=(
            [cfg.model_dump() for cfg in body.round_configuration]
            if body and body.round_configuration
            else None
        ),
        deselected_rounds=body.deselected_rounds if body else None,
    )


@router.post("/role-assessment/generate", response_model=CompanyPatternResponse, status_code=status.HTTP_201_CREATED)
def generate_role_assessment(
    payload: RoleAssessmentGenerationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a role-specific draft pattern for an explicit no-history request."""
    _require_tpo_or_admin(current_user)
    return generate_role_assessment_pattern(db, payload, current_user.id)


# ── 7. Seed EDI5 benchmark fallback ──────────────────────────────────

@router.post("/pattern/seed-fallback", response_model=CompanyHistoricalDataResponse, status_code=status.HTTP_201_CREATED)
def seed_benchmark_source(
    payload: SeedBenchmarkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Explicitly seed an EDI5 benchmark historical record for a company + role."""
    _require_tpo_or_admin(current_user)
    return seed_edi5_fallback_data(
        db=db,
        company_name=payload.company_name,
        target_role=payload.target_role,
        created_by_id=current_user.id,
    )


# ── 8. List available EDI5 benchmarks ─────────────────────────────────

@router.get("/benchmarks")
def get_benchmarks(
    current_user: User = Depends(get_current_user),
):
    """List available pre-seeded EDI5 benchmarks."""
    _require_tpo_or_admin(current_user)
    return list_available_benchmarks()


# ── 9. List all patterns ──────────────────────────────────────────────

@router.get("/pattern", response_model=List[CompanyPatternResponse])
def list_all_patterns(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all derived company+role patterns."""
    _require_tpo_or_admin(current_user)
    return list_patterns(db=db)


# ── 10. Get pattern for specific company + role ───────────────────────

@router.get("/pattern/{company_name}/{target_role}", response_model=CompanyPatternResponse)
def get_company_pattern(
    company_name: str,
    target_role: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the derived pattern for a specific company + role."""
    _require_tpo_or_admin(current_user)
    return get_pattern(db=db, company_name=company_name, target_role=target_role)


# ── 11. Review & Approve structured pattern ───────────────────────────

@router.post("/pattern/{company_name}/{target_role}/review", response_model=CompanyPatternResponse)
def review_company_pattern(
    company_name: str,
    target_role: str,
    payload: ReviewPatternRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Review and approve (or flag for revision) the structured pattern."""
    _require_tpo_or_admin(current_user)
    return review_pattern(
        db=db,
        company_name=company_name,
        target_role=target_role,
        review_status=payload.status,
        notes=payload.notes,
        reviewer_email=current_user.email,
    )


# ── 12. Generate / Recalculate Blueprint (Phase 4B) ───────────────────

@router.post("/blueprint/generate", response_model=CompanyBlueprintResponse)
def generate_assessment_blueprint(
    body: Optional[GenerateBlueprintRequest] = None,
    company_name: Optional[str] = Query(None),
    target_role: Optional[str] = Query(None),
    force: Optional[bool] = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate (or recalculate) an assessment blueprint from an approved 4A pattern."""
    _require_tpo_or_admin(current_user)
    c_name = body.company_name if body and body.company_name else company_name
    t_role = body.target_role if body and body.target_role else target_role
    force_val = (body.force if body and body.force is not None else force) or False
    if not c_name or not t_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="company_name and target_role are required.",
        )
    return generate_blueprint_from_pattern(
        db=db,
        company_name=c_name,
        target_role=t_role,
        created_by_id=current_user.id,
        force=force_val,
    )


# ── 13. List Blueprints ───────────────────────────────────────────────

@router.get("/blueprint", response_model=List[CompanyBlueprintResponse])
def list_all_blueprints(
    company_name: Optional[str] = Query(None, description="Filter by company (partial)"),
    target_role: Optional[str] = Query(None, description="Filter by role (partial)"),
    status: Optional[str] = Query(None, description="Filter by status (draft|approved)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all company blueprints."""
    _require_tpo_or_admin(current_user)
    return list_blueprints(
        db=db,
        company_name=company_name,
        target_role=target_role,
        status_filter=status,
    )


# ── 14. Get Blueprint for specific company + role ─────────────────────

@router.get("/blueprint/{company_name}/{target_role}", response_model=CompanyBlueprintResponse)
def get_company_blueprint(
    company_name: str,
    target_role: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get the assessment blueprint for a specific company + role."""
    _require_tpo_or_admin(current_user)
    return get_blueprint(db=db, company_name=company_name, target_role=target_role)


# ── 15. Edit Blueprint ────────────────────────────────────────────────

@router.put("/blueprint/{company_name}/{target_role}", response_model=CompanyBlueprintResponse)
def update_company_blueprint(
    company_name: str,
    target_role: str,
    payload: UpdateBlueprintRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Edit/update round configurations, durations, questions, topic weights, or difficulty."""
    _require_tpo_or_admin(current_user)
    return update_blueprint(
        db=db,
        company_name=company_name,
        target_role=target_role,
        payload=payload,
        user_id=current_user.id,
    )


# ── 16. Approve Blueprint ─────────────────────────────────────────────

@router.post("/blueprint/{company_name}/{target_role}/approve", response_model=CompanyBlueprintResponse)
def approve_company_blueprint(
    company_name: str,
    target_role: str,
    payload: ReviewBlueprintRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve assessment blueprint and transition status to 'approved'."""
    _require_tpo_or_admin(current_user)
    return approve_blueprint(
        db=db,
        company_name=company_name,
        target_role=target_role,
        status_val=payload.status,
        notes=payload.notes,
        user_id=current_user.id,
    )


# ── 17. Delete Blueprint ──────────────────────────────────────────────

@router.delete("/blueprint/{blueprint_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company_blueprint(
    blueprint_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete a company assessment blueprint."""
    _require_tpo_or_admin(current_user)
    delete_blueprint(db=db, blueprint_id=blueprint_id)


# ── 18. Question Pool Status (pre-candidate LLM pool) ──────────────────

@router.get("/blueprint/{company_name}/{target_role}/question-pool/status")
def get_question_pool_status(
    company_name: str,
    target_role: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return per-round generated question-pool status for an approved blueprint."""
    _require_tpo_or_admin(current_user)
    from app.services.question_pool_generation_service import (
        question_pool_generation_service,
    )

    blueprint = get_blueprint(db=db, company_name=company_name, target_role=target_role)
    if blueprint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No blueprint for '{company_name}' - '{target_role}'.",
        )
    return {
        "blueprint_id": blueprint.id,
        "blueprint_version": blueprint.version,
        "rounds": question_pool_generation_service.list_pool_statuses(db, blueprint),
    }


# ── 19. Generate Question Pool (pre-candidate LLM pool) ────────────────

@router.post("/blueprint/{company_name}/{target_role}/question-pool/generate")
def generate_question_pool(
    company_name: str,
    target_role: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate + validate question pools for every round of an approved blueprint.

    LLM generation happens ONLY here (TPO-triggered, before any candidate runs);
    candidate distribution reuses the persisted, validated content.
    """
    _require_tpo_or_admin(current_user)
    from app.services.question_pool_generation_service import (
        question_pool_generation_service,
    )

    blueprint = get_blueprint(db=db, company_name=company_name, target_role=target_role)
    if blueprint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No blueprint for '{company_name}' - '{target_role}'.",
        )
    return question_pool_generation_service.generate_for_blueprint(
        db=db,
        blueprint=blueprint,
        created_by_id=current_user.id,
    )


# ── 20. Generate Competency Configuration Suggestions ─────────────────────

@router.post("/blueprint/{company_name}/{target_role}/competencies/generate")
def generate_competency_suggestions(
    company_name: str,
    target_role: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate role-specific competency suggestions with weights and topic associations.

    Uses the approved blueprint's canonical topics and the pattern's role understanding
    to produce editable competency suggestions. Does not persist; returns suggestions
    for TPO review and explicit save via the existing blueprint update endpoint.
    """
    _require_tpo_or_admin(current_user)
    from app.services.groq_service import GroqService
    from app.config.settings import settings

    company = company_name.strip()
    role = target_role.strip()

    blueprint = get_blueprint(db=db, company_name=company, target_role=role)
    if blueprint is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No blueprint for '{company}' - '{role}'.",
        )

    # Must be approved or draft blueprint to generate competencies
    if blueprint.status not in ("draft", "approved"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Blueprint status '{blueprint.status}' does not support competency generation.",
        )

    bp_data = blueprint.blueprint_data or {}
    provenance = bp_data.get("source_provenance", {})
    is_llm_role = provenance.get("generation_method") == "llm_role_assessment"

    # Gather canonical topics from blueprint rounds
    blueprint_topics = []
    round_info = []
    for round_config in bp_data.get("rounds", []):
        rt = round_config.get("round_type")
        topics = [t.get("topic") for t in round_config.get("topics", []) if t.get("topic")]
        qc = round_config.get("question_count", 0)
        blueprint_topics.extend(topics)
        round_info.append({"round_type": rt, "topics": topics, "question_count": qc})

    # Deduplicate topics
    seen = set()
    canonical_topics = []
    for t in blueprint_topics:
        key = t.strip().casefold()
        if key not in seen:
            seen.add(key)
            canonical_topics.append(t.strip())

    # Get existing competency names from pattern's role_understanding if available
    existing_competencies = []
    if is_llm_role:
        pattern = (
            db.query(CompanyPattern)
            .filter(
                func.lower(func.trim(CompanyPattern.company_name)) == company.lower(),
                func.lower(func.trim(CompanyPattern.target_role)) == role.lower(),
            )
            .first()
        )
        if pattern and pattern.pattern_data:
            role_understanding = pattern.pattern_data.get("role_understanding", {})
            existing_competencies = role_understanding.get("competencies", []) or []

    if not settings.GROQ_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "GROQ_UNAVAILABLE", "message": "GROQ_API_KEY is not configured."},
        )

    try:
        client = GroqService(settings.GROQ_API_KEY)
        spec = {
            "company_name": company,
            "target_role": role,
            "blueprint_topics": canonical_topics,
            "existing_competencies": existing_competencies,
            "round_info": round_info,
        }
        suggestions = client.generate_competency_configuration(spec)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "COMPETENCY_GENERATION_FAILED", "message": str(exc)},
        ) from exc

    return {
        "company_name": company,
        "target_role": role,
        "blueprint_id": blueprint.id,
        "blueprint_version": blueprint.version,
        "competencies": suggestions,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
