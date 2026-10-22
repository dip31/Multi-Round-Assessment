"""
Tests for Phase 4B: Company Assessment Blueprint Generation.

Covers:
 1. Non-TPO / Student cannot generate, edit, or approve blueprint (403).
 2. Generating blueprint fails (404) if no pattern exists for company+role.
 3. Generating blueprint fails (400) if pattern is not approved by TPO.
 4. Generating blueprint succeeds from an approved 4A pattern with multiple rounds:
    - Verifies round ordering, duration, question count, question types.
    - Verifies topic distribution and weights (normalized to 100%).
    - Verifies difficulty distribution.
 5. Sparse evidence / fallback handling:
    - Unobserved round or topic attributes are marked as fallback (is_default_fallback=True, is_default=True).
 6. TPO can retrieve single blueprint and list all blueprints.
 7. TPO can edit round configurations, durations, question counts, and topic weights.
 8. TPO can approve the blueprint (status transitions from 'draft' to 'approved').
 9. Blueprint recalculation creates a new version while preserving company+role association.
 10. TPO can delete a blueprint.
"""

import io
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.db import get_db
from app.main import app as application


# ── SQLite JSONB shim ─────────────────────────────────────────────────
@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"


# ── In-memory SQLite engine ───────────────────────────────────────────
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# Force-import all models so Base.metadata is complete
import app.models.user
import app.models.company_data
import app.models.mock_drive

Base.metadata.create_all(bind=engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module", autouse=True)
def setup_blueprint_db():
    application.dependency_overrides[get_db] = override_get_db
    yield
    application.dependency_overrides.pop(get_db, None)


client = TestClient(application)


# ── Helpers ───────────────────────────────────────────────────────────

def _register_and_login(role: str) -> dict:
    uid = uuid.uuid4().hex[:8]
    email = f"phase4b_{role}_{uid}@test.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={
            "name": f"Test {role.capitalize()}",
            "email": email,
            "password": "Password@123",
            "role": role,
        },
    )
    assert reg.status_code in (200, 201), f"Register failed for {role}: {reg.text}"
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "Password@123"},
    )
    assert login.status_code == 200, f"Login failed for {role}: {login.text}"
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def tpo_headers():
    return _register_and_login("tpo")


@pytest.fixture(scope="module")
def student_headers():
    return _register_and_login("student")


BASE_HISTORICAL_URL = "/api/v1/tpo/company-data/historical"
BASE_PATTERN_URL = "/api/v1/tpo/company-data/pattern"
BASE_BLUEPRINT_URL = "/api/v1/tpo/company-data/blueprint"


# ── 1. RBAC Tests ─────────────────────────────────────────────────────

def test_student_cannot_generate_or_view_blueprint(student_headers):
    res = client.post(
        f"{BASE_BLUEPRINT_URL}/generate",
        json={"company_name": "Google", "target_role": "Software Engineer"},
        headers=student_headers,
    )
    assert res.status_code == 403

    res_get = client.get(f"{BASE_BLUEPRINT_URL}/Google/Software Engineer", headers=student_headers)
    assert res_get.status_code == 403


# ── 2. Validation & Approval Prerequisite ─────────────────────────────

def test_generate_blueprint_fails_when_pattern_missing(tpo_headers):
    res = client.post(
        f"{BASE_BLUEPRINT_URL}/generate",
        json={"company_name": "NonExistentCo", "target_role": "Architect"},
        headers=tpo_headers,
    )
    assert res.status_code == 404
    assert "No structured pattern found" in res.json()["detail"]


def test_generate_blueprint_fails_when_pattern_not_approved(tpo_headers):
    # Add historical data and generate pattern for Uber
    client.post(
        BASE_HISTORICAL_URL,
        json={
            "company_name": "Uber",
            "target_role": "Backend Engineer",
            "label": "Uber 2024",
            "raw_data": {
                "rounds": ["coding", "technical_interview"],
                "topics": ["Dynamic Programming", "System Design", "Distributed Systems", "SQL"],
                "difficulty": "hard",
            },
        },
        headers=tpo_headers,
    )
    # Generate pattern (which starts as pending_review)
    pat_res = client.post(
        f"{BASE_PATTERN_URL}/generate?company_name=Uber&target_role=Backend Engineer",
        headers=tpo_headers,
    )
    assert pat_res.status_code == 200

    # Attempt to generate blueprint without approval -> must fail 400
    bp_res = client.post(
        f"{BASE_BLUEPRINT_URL}/generate",
        json={"company_name": "Uber", "target_role": "Backend Engineer"},
        headers=tpo_headers,
    )
    assert bp_res.status_code == 400
    assert "must be approved by TPO" in bp_res.json()["detail"]


# ── 3. Successful Generation from Approved Pattern ────────────────────

def test_generate_blueprint_from_approved_pattern(tpo_headers):
    company = "Google"
    role = "Software Engineer"

    # 1. Add historical sources for Google
    client.post(
        BASE_HISTORICAL_URL,
        json={
            "company_name": company,
            "target_role": role,
            "label": "Google Campus Drive 2024",
            "raw_data": {
                "year": 2024,
                "rounds": ["aptitude", "coding", "technical_interview", "hr_interview"],
                "topics": [
                    "Data Structures & Algorithms", "Dynamic Programming", "Graphs & Graph Algorithms",
                    "Operating Systems", "System Design", "Behavioral & Leadership Principles",
                    "Quantitative Aptitude", "Logical Reasoning",
                ],
                "difficulty": "hard",
                "round_patterns": {
                    "aptitude": {"duration_minutes": 60, "question_count": 30, "focus_areas": ["Quantitative Aptitude", "Logical Reasoning"]},
                    "coding": {"duration_minutes": 90, "question_count": 2, "focus_areas": ["Data Structures & Algorithms", "Dynamic Programming"]},
                    "technical_interview": {"duration_minutes": 45, "question_count": 3, "focus_areas": ["System Design", "Operating Systems"]},
                    "hr_interview": {"duration_minutes": 30, "question_count": 3, "focus_areas": ["Behavioral & Leadership Principles"]},
                },
            },
        },
        headers=tpo_headers,
    )

    # 2. Generate and Approve the Pattern
    client.post(
        f"{BASE_PATTERN_URL}/generate?company_name={company}&target_role={role}",
        headers=tpo_headers,
    )
    review_res = client.post(
        f"{BASE_PATTERN_URL}/{company}/{role}/review",
        json={"status": "approved", "notes": "Approved pattern for Google SWE"},
        headers=tpo_headers,
    )
    assert review_res.status_code == 200

    # 3. Generate Blueprint
    bp_res = client.post(
        f"{BASE_BLUEPRINT_URL}/generate",
        json={"company_name": company, "target_role": role},
        headers=tpo_headers,
    )
    assert bp_res.status_code == 200
    bp = bp_res.json()

    assert bp["company_name"] == company
    assert bp["target_role"] == role
    assert bp["status"] == "draft"
    assert bp["version"] == 1
    assert bp["confidence_level"] in ("medium", "high")

    bdata = bp["blueprint_data"]
    assert bdata["source_provenance"]["classification"] == "company_specific_historical_evidence"
    assert bdata["empirical_evidence_sources_count"] == 1
    assert len(bdata["rounds"]) == 4

    # Check Aptitude Round
    apt_round = next(r for r in bdata["rounds"] if r["round_type"] == "aptitude")
    assert apt_round["round_order"] == 1
    assert apt_round["time_limit_minutes"] == 60
    assert apt_round["question_count"] == 30
    assert apt_round["question_types"] == ["MCQ"]

    # Check Coding Round
    code_round = next(r for r in bdata["rounds"] if r["round_type"] == "coding")
    assert code_round["round_order"] == 2
    assert code_round["time_limit_minutes"] == 90
    assert code_round["question_count"] == 2
    assert code_round["question_types"] == ["Coding"]
    assert len(code_round["topics"]) >= 2
    # Verify weights sum up to 100%
    total_code_weight = sum(t["weight_pct"] for t in code_round["topics"])
    assert round(total_code_weight, 1) == 100.0

    # Check Technical Interview Round
    tech_round = next(r for r in bdata["rounds"] if r["round_type"] == "technical_interview")
    assert tech_round["round_order"] == 3
    assert tech_round["time_limit_minutes"] == 45
    assert len(tech_round["topics"]) >= 1


# ── 4. Fallback Handling for Sparse Evidence ──────────────────────────

def test_sparse_evidence_fallback_handling(tpo_headers):
    # Microsoft with pre-seeded fallback
    company = "Microsoft"
    role = "Software Engineer"

    # Generate pattern with fallback enabled
    client.post(
        f"{BASE_PATTERN_URL}/generate?company_name={company}&target_role={role}&use_fallback=true",
        headers=tpo_headers,
    )
    # Approve pattern
    client.post(
        f"{BASE_PATTERN_URL}/{company}/{role}/review",
        json={"status": "approved", "notes": "Approved fallback pattern"},
        headers=tpo_headers,
    )

    # Generate Blueprint
    res = client.post(
        f"{BASE_BLUEPRINT_URL}/generate",
        json={"company_name": company, "target_role": role},
        headers=tpo_headers,
    )
    assert res.status_code == 200
    bp = res.json()
    bdata = bp["blueprint_data"]
    assert bdata["source_provenance"]["classification"] == "pre_seeded_benchmark"
    assert bdata["source_provenance"]["explicit_fallback_requested"] is True
    assert bp["evidence_sources_count"] == 0

    # Check that fallback rounds contain valid canonical topics
    for r in bdata["rounds"]:
        assert r["time_limit_minutes"] > 0
        assert r["question_count"] > 0
        assert len(r["topics"]) > 0
        total_weight = sum(t["weight_pct"] for t in r["topics"])
        assert round(total_weight, 1) == 100.0


def test_explicit_generic_data_analyst_fallback_blueprint_has_provenance(tpo_headers):
    company, role = "DataAnalystFallbackCo", "Data Analyst"
    generated = client.post(
        f"{BASE_PATTERN_URL}/generate?company_name={company}&target_role={role}&use_fallback=true",
        headers=tpo_headers,
    )
    assert generated.status_code == 200
    client.post(
        f"{BASE_PATTERN_URL}/{company}/{role}/review",
        json={"status": "approved"},
        headers=tpo_headers,
    )
    result = client.post(
        f"{BASE_BLUEPRINT_URL}/generate",
        json={"company_name": company, "target_role": role},
        headers=tpo_headers,
    )
    assert result.status_code == 200
    blueprint = result.json()
    assert blueprint["evidence_sources_count"] == 0
    assert blueprint["blueprint_data"]["source_provenance"]["classification"] == "generic_fallback"


# ── 5. TPO View, Edit, and Approval Workflow ──────────────────────────

def test_tpo_edit_and_approve_blueprint(tpo_headers):
    company = "Google"
    role = "Software Engineer"

    # 1. Fetch single blueprint
    get_res = client.get(f"{BASE_BLUEPRINT_URL}/{company}/{role}", headers=tpo_headers)
    assert get_res.status_code == 200
    bp = get_res.json()
    assert bp["status"] == "draft"

    # 2. Edit blueprint (change coding time to 75 mins, 3 questions)
    rounds = bp["blueprint_data"]["rounds"]
    for r in rounds:
        if r["round_type"] == "coding":
            r["time_limit_minutes"] = 75
            r["question_count"] = 3

    edit_res = client.put(
        f"{BASE_BLUEPRINT_URL}/{company}/{role}",
        json={
            "rounds": rounds,
            "overall_difficulty": "hard",
            "review_notes": "Updated coding duration for competitive programming round.",
        },
        headers=tpo_headers,
    )
    assert edit_res.status_code == 200
    updated_bp = edit_res.json()
    coding_rnd = next(r for r in updated_bp["blueprint_data"]["rounds"] if r["round_type"] == "coding")
    assert coding_rnd["time_limit_minutes"] == 75
    assert coding_rnd["question_count"] == 3
    assert updated_bp["review_notes"] == "Updated coding duration for competitive programming round."

    # 3. Approve blueprint
    appr_res = client.post(
        f"{BASE_BLUEPRINT_URL}/{company}/{role}/approve",
        json={"status": "approved", "notes": "Approved for 2024 placement season."},
        headers=tpo_headers,
    )
    assert appr_res.status_code == 200
    approved_bp = appr_res.json()
    assert approved_bp["status"] == "approved"
    assert approved_bp["review_notes"] == "Approved for 2024 placement season."
    assert approved_bp["reviewed_at"] is not None

    # 4. List blueprints and verify approved status
    list_res = client.get(f"{BASE_BLUEPRINT_URL}?status=approved", headers=tpo_headers)
    assert list_res.status_code == 200
    approved_list = list_res.json()
    assert any(b["company_name"] == company and b["target_role"] == role for b in approved_list)


# ── 6. Recalculation & Deletion ───────────────────────────────────────

def test_recalculate_and_delete_blueprint(tpo_headers):
    company = "Google"
    role = "Software Engineer"

    # Recalculate blueprint -> should bump version
    recalc_res = client.post(
        f"{BASE_BLUEPRINT_URL}/generate",
        json={"company_name": company, "target_role": role, "force": True},
        headers=tpo_headers,
    )
    assert recalc_res.status_code == 200
    recalced = recalc_res.json()
    assert recalced["version"] == 2
    assert recalced["status"] == "draft"  # resets to draft for new review

    # Delete blueprint
    bp_id = recalced["id"]
    del_res = client.delete(f"{BASE_BLUEPRINT_URL}/{bp_id}", headers=tpo_headers)
    assert del_res.status_code == 204

    # Verify 404 after deletion
    get_res = client.get(f"{BASE_BLUEPRINT_URL}/{company}/{role}", headers=tpo_headers)
    assert get_res.status_code == 404


# ── 7. GET by exact identity (reported "Barclays" 404) ────────────────

def test_get_blueprint_returns_persisted_row_for_exact_ui_identity(tpo_headers):
    """GET /blueprint/{company}/{role} must return the persisted row for the
    exact values the UI submits (Barclays manual testing / Database engineer),
    must also match a stored row carrying edge whitespace, and must keep
    returning 404 for any near-miss identity."""
    from app.models.company_data import CompanyBlueprint
    from app.models.user import User

    db = TestingSessionLocal()
    try:
        tpo = db.query(User).filter(User.role == "tpo").first()
        assert tpo is not None
        db.add(CompanyBlueprint(
            company_name="Barclays manual testing",
            target_role="Database engineer",
            status="approved",
            version=1,
            blueprint_data={
                "company_name": "Barclays manual testing",
                "target_role": "Database engineer",
                "status": "approved",
                "version": 1,
                "rounds": [],
            },
            confidence_level="medium",
            evidence_sources_count=2,
            created_by_id=tpo.id,
        ))
        # Legacy row whose STORED identity carries edge whitespace.
        db.add(CompanyBlueprint(
            company_name="  Contoso Ltd  ",
            target_role="  Data Engineer  ",
            status="approved",
            version=1,
            blueprint_data={"company_name": "Contoso Ltd", "target_role": "Data Engineer",
                            "status": "approved", "version": 1, "rounds": []},
            confidence_level="medium",
            evidence_sources_count=0,
            created_by_id=tpo.id,
        ))
        db.commit()
    finally:
        db.close()

    res = client.get(
        f"{BASE_BLUEPRINT_URL}/Barclays manual testing/Database engineer",
        headers=tpo_headers,
    )
    assert res.status_code == 200
    bp = res.json()
    assert bp["company_name"] == "Barclays manual testing"
    assert bp["target_role"] == "Database engineer"
    assert bp["status"] == "approved"
    assert bp["version"] == 1

    # Edge whitespace on the stored identity does not hide the row.
    res = client.get(f"{BASE_BLUEPRINT_URL}/Contoso Ltd/Data Engineer", headers=tpo_headers)
    assert res.status_code == 200
    assert res.json()["company_name"] == "  Contoso Ltd  "
    assert res.json()["target_role"] == "  Data Engineer  "

    # Identity comparison stays EXACT (case-insensitive, trimmed): near-miss
    # company, role mismatch, and different casing on the role still 404.
    near_miss = client.get(
        f"{BASE_BLUEPRINT_URL}/Barclays manual testings/Database engineer",
        headers=tpo_headers,
    )
    assert near_miss.status_code == 404
    role_mismatch = client.get(
        f"{BASE_BLUEPRINT_URL}/Barclays manual testing/Database testers",
        headers=tpo_headers,
    )
    assert role_mismatch.status_code == 404
    company_mismatch = client.get(
        f"{BASE_BLUEPRINT_URL}/Contoso Ltd/Data Engineer II",
        headers=tpo_headers,
    )
    assert company_mismatch.status_code == 404


# -- 11. LLM role-assessment blueprint is never recalculated (409) -----

def test_role_assessment_blueprint_recalculate_conflicts_and_preserves_version(tpo_headers):
    """Reported bug: the UI's generate/recalculate call returned 409 for an LLM
    role-assessment blueprint. The conflict must protect the existing approved
    blueprint: version/status/blueprint_data unchanged, no duplicate row, and
    its generated question pools stay attached to the same blueprint version.
    Reads keep working."""
    from app.models.company_data import CompanyBlueprint, CompanyPattern
    from app.models.question_pool_generation import GeneratedQuestionPool
    from app.models.user import User

    company, role = "Zensar Locked", "Software developer"
    provenance = {
        "classification": "llm_role_assessment",
        "generation_method": "llm_role_assessment",
        "selection_status": "role_compatible_evidence_found",
        "empirical_source_count": 0,
        "historical_evidence_used": False,
    }
    rounds = [{
        "round_type": "aptitude",
        "question_count": 15,
        "time_limit_minutes": 45,
        "topics": [{"topic": "Cloud Fundamentals", "weight_pct": 100}],
        "difficulty_distribution": {"easy": 0.25, "medium": 0.5, "hard": 0.25},
    }]

    db = TestingSessionLocal()
    try:
        tpo = db.query(User).filter(User.role == "tpo").first()
        assert tpo is not None
        db.add(CompanyPattern(
            company_name=company,
            target_role=role,
            source_count=0,
            pattern_data={"review_status": "approved", "source_provenance": provenance},
            created_by_id=tpo.id,
        ))
        bp = CompanyBlueprint(
            company_name=company,
            target_role=role,
            status="approved",
            version=1,
            blueprint_data={
                "company_name": company,
                "target_role": role,
                "status": "approved",
                "version": 1,
                "rounds": rounds,
                "source_provenance": provenance,
            },
            confidence_level="medium",
            evidence_sources_count=0,
            created_by_id=tpo.id,
        )
        db.add(bp)
        db.commit()
        db.refresh(bp)
        blueprint_id = bp.id
        original_data = dict(bp.blueprint_data)
        db.add(GeneratedQuestionPool(
            blueprint_id=bp.id,
            blueprint_version=1,
            company_name=company,
            target_role=role,
            round_type="aptitude",
            status="complete",
            required_count=30,
            validated_count=30,
            content=[],
            created_by_id=tpo.id,
        ))
        db.commit()
    finally:
        db.close()

    # Both the first-time call and the explicit recalculation call are refused.
    for force in (True, False):
        res = client.post(
            f"{BASE_BLUEPRINT_URL}/generate",
            json={"company_name": company, "target_role": role, "force": force},
            headers=tpo_headers,
        )
        assert res.status_code == 409, res.text
        assert res.json()["detail"] == (
            "An LLM role assessment blueprint already exists; it was not overwritten."
        )

    db = TestingSessionLocal()
    try:
        rows = (
            db.query(CompanyBlueprint)
            .filter(CompanyBlueprint.company_name == company,
                    CompanyBlueprint.target_role == role)
            .all()
        )
        assert len(rows) == 1
        stored = rows[0]
        assert stored.version == 1
        assert stored.status == "approved"
        assert dict(stored.blueprint_data) == original_data

        pool = (
            db.query(GeneratedQuestionPool)
            .filter(GeneratedQuestionPool.company_name == company,
                    GeneratedQuestionPool.round_type == "aptitude")
            .one()
        )
        assert pool.blueprint_id == blueprint_id
        assert pool.blueprint_version == 1
        assert pool.status == "complete"
        assert pool.required_count == 30
        assert pool.validated_count == 30
    finally:
        db.close()

    view = client.get(f"{BASE_BLUEPRINT_URL}/{company}/{role}", headers=tpo_headers)
    assert view.status_code == 200
    assert view.json()["version"] == 1
    assert view.json()["status"] == "approved"


# -- 12. Competency edits: invalid -> 422 (not 500), null -> preserve ----

def test_blueprint_competency_edit_returns_422_not_500(tpo_headers):
    from app.models.company_data import CompanyBlueprint
    from app.models.user import User

    company, role = "Competency Edit Co", "Data Engineer"
    stored = [{
        "id": "quant", "name": "Quantitative",
        "weight_pct": 100, "topics": ["Quantitative Aptitude"],
    }]
    db = TestingSessionLocal()
    try:
        tpo = db.query(User).filter(User.role == "tpo").first()
        assert tpo is not None
        db.add(CompanyBlueprint(
            company_name=company, target_role=role, status="approved", version=1,
            blueprint_data={
                "company_name": company, "target_role": role, "status": "approved",
                "version": 1, "rounds": [], "competencies": stored,
            },
            confidence_level="medium", evidence_sources_count=0, created_by_id=tpo.id,
        ))
        db.commit()
    finally:
        db.close()

    # Invalid weights via blueprint_data must be a structured 422, not a 500.
    res = client.put(
        f"{BASE_BLUEPRINT_URL}/{company}/{role}",
        json={"blueprint_data": {"competencies": [
            {"name": "A", "weight_pct": 50, "topics": ["T1"]},
            {"name": "B", "weight_pct": 30, "topics": ["T2"]},
        ]}},
        headers=tpo_headers,
    )
    assert res.status_code == 422, res.text

    # An explicitly empty set is rejected too.
    res = client.put(
        f"{BASE_BLUEPRINT_URL}/{company}/{role}",
        json={"blueprint_data": {"competencies": []}},
        headers=tpo_headers,
    )
    assert res.status_code == 422, res.text

    # Omitted competencies preserve the stored configuration.
    res = client.put(
        f"{BASE_BLUEPRINT_URL}/{company}/{role}",
        json={"overall_difficulty": "hard"},
        headers=tpo_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["blueprint_data"]["competencies"] == stored

    # Explicit JSON null preserves it as well (documented policy).
    res = client.put(
        f"{BASE_BLUEPRINT_URL}/{company}/{role}",
        json={"blueprint_data": {"competencies": None}},
        headers=tpo_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["blueprint_data"]["competencies"] == stored
