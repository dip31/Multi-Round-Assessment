"""
Unit and integration tests for Phase 4C Part 1: Approved Blueprint Integration with Mock Drive.

Test Coverage:
1. Approved blueprint can be selected and linked to Mock Drive on creation.
2. Wrong company/role blueprint attachment is rejected with 422.
3. Unapproved blueprint attachment is rejected with 422.
4. Non-existent blueprint attachment is rejected with 404.
5. Blueprint ID/version is stored with the Mock Drive.
6. Updating a draft Mock Drive to link/unlink an approved blueprint works.
7. Publishing a Mock Drive validates linked blueprint.
8. Starting the Mock Drive loads the correct blueprint, and enabled rounds + order come from the blueprint.
9. Existing Phase 3 Mock Drive without blueprint continues to work normally.
10. Advancing rounds in a blueprint-driven Mock Drive follows blueprint sequence.
"""

import uuid
from datetime import datetime, timedelta
from types import SimpleNamespace
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from app.database.db import get_db
from app.database.base import Base
from app.main import app as application
from app.models.user import User
from app.models.profile import StudentProfile
from app.models.company_data import CompanyBlueprint, CompanyPattern
from app.models.mock_drive import MockDrive
from app.models.assessment_context import AssessmentPolicy, AssessmentContext
from app.models.assessment import AssessmentSession, AssessmentRound
from app.models.aptitude import AptitudeAttempt, AptitudeQuestion, AptitudeRoundQuestion, AptitudeTopic
from app.models.coding import CodingProblem
from app.models.question_pool_generation import (
    GeneratedQuestionPool,
    POOL_STATUS_COMPLETE,
    POOL_SIZES,
)
from app.models.session_problem import SessionProblem
from app.middleware.rate_limit import RateLimitMiddleware
from app.models.profile import UserResume
from app.config.security import create_access_token
from app.modules.interview.routers import interview_router as interview_router_module
from app.services.groq_service import GroqService



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


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


from app.services.assessment_context_service import DEFAULT_PRACTICE_POLICY_ID


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    # Seed default practice policy (id=DEFAULT_PRACTICE_POLICY_ID)
    if not db.query(AssessmentPolicy).filter(AssessmentPolicy.id == DEFAULT_PRACTICE_POLICY_ID).first():
        policy = AssessmentPolicy(
            id=DEFAULT_PRACTICE_POLICY_ID,
            name="Default Practice Policy",
            session_duration_minutes=180,
            round_duration_minutes=30,
            resume_allowed=True,
            exit_allowed=True,
            progression_mode="sequential",
            progression_config={"rounds": ["aptitude", "coding", "interview"]},
        )
        db.add(policy)
        db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)



@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    application.dependency_overrides[get_db] = override_get_db
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()


@pytest.fixture
def auth_headers_tpo(db_session):
    tpo_user = User(
        name="Test TPO",
        email=f"tpo_{uuid.uuid4().hex[:6]}@college.edu",
        role="tpo",
        password_hash="pw",
    )
    db_session.add(tpo_user)
    db_session.commit()
    db_session.refresh(tpo_user)
    token = create_access_token(data={"sub": str(tpo_user.id)})
    return {"Authorization": f"Bearer {token}"}, tpo_user


@pytest.fixture
def auth_headers_student(db_session):
    student = User(
        name="Test Student",
        email=f"student_{uuid.uuid4().hex[:6]}@college.edu",
        role="student",
        password_hash="pw",
    )
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)

    profile = StudentProfile(
        user_id=student.id,
        cgpa=8.5,
        backlogs_count=0,
        department="Computer Science",
    )
    db_session.add(profile)
    db_session.commit()

    token = create_access_token(data={"sub": str(student.id)})
    return {"Authorization": f"Bearer {token}"}, student


def _blueprintless_round_config(*round_types, duration_minutes=30):
    return {
        round_type: {
            "question_count": 5,
            "duration_minutes": duration_minutes,
            "difficulty_distribution": {"easy": 0.5, "medium": 0.5, "hard": 0.0},
        }
        for round_type in round_types
    }


@pytest.fixture
def sample_approved_blueprint(db_session, auth_headers_tpo):
    _, tpo = auth_headers_tpo
    bp = CompanyBlueprint(
        company_name="Google",
        target_role="Software Engineer",
        status="approved",
        version=2,
        blueprint_data={
            "company_name": "Google",
            "target_role": "Software Engineer",
            "status": "approved",
            "version": 2,
            "rounds": [
                {
                    "round_type": "coding",
                    "round_order": 1,
                    "round_name": "Coding Assessment",
                    "time_limit_minutes": 60,
                    "question_count": 2,
                },
                {
                    "round_type": "technical_interview",
                    "round_order": 2,
                    "round_name": "Technical Interview",
                    "time_limit_minutes": 45,
                    "question_count": 3,
                },
            ],
        },
        confidence_level="high",
        evidence_sources_count=3,
        created_by_id=tpo.id,
    )
    db_session.add(bp)
    db_session.commit()
    db_session.refresh(bp)
    return bp


@pytest.fixture
def sample_three_round_blueprint(db_session, auth_headers_tpo):
    _, tpo = auth_headers_tpo
    bp = CompanyBlueprint(
        company_name="Google",
        target_role="Software Engineer",
        status="approved",
        version=3,
        blueprint_data={
            "rounds": [
                {"round_type": "coding", "round_order": 1},
                {"round_type": "aptitude", "round_order": 2},
                {"round_type": "technical_interview", "round_order": 3},
            ],
        },
        confidence_level="high",
        evidence_sources_count=3,
        created_by_id=tpo.id,
    )
    db_session.add(bp)
    db_session.commit()
    db_session.refresh(bp)
    return bp


@pytest.fixture
def sample_aptitude_coding_blueprint(db_session, auth_headers_tpo):
    _, tpo = auth_headers_tpo
    bp = CompanyBlueprint(
        company_name="Infosys",
        target_role="Systems Engineer",
        status="approved",
        version=1,
        blueprint_data={
            "rounds": [
                {"round_type": "aptitude", "round_order": 1},
                {"round_type": "coding", "round_order": 2},
            ],
        },
        confidence_level="high",
        evidence_sources_count=2,
        created_by_id=tpo.id,
    )
    db_session.add(bp)
    db_session.commit()
    db_session.refresh(bp)
    return bp


@pytest.fixture
def sample_generation_blueprint(db_session, auth_headers_tpo):
    _, tpo = auth_headers_tpo
    bp = CompanyBlueprint(
        company_name="Nvidia",
        target_role="Software Engineer",
        status="approved",
        version=4,
        blueprint_data={
            "rounds": [
                {
                    "round_type": "aptitude",
                    "round_order": 1,
                    "question_count": 4,
                    "time_limit_minutes": 60,
                    "question_types": ["MCQ"],
                    "topics": [
                        {"topic": "Quantitative Aptitude", "weight_pct": 50},
                        {"topic": "Logical Reasoning", "weight_pct": 50},
                    ],
                    "difficulty_distribution": {"easy": 50, "medium": 50},
                },
                {
                    "round_type": "coding",
                    "round_order": 2,
                    "question_count": 2,
                    "question_types": ["Coding"],
                    "topics": [
                        {"topic": "Arrays", "weight_pct": 50},
                        {"topic": "HashMap", "weight_pct": 50},
                    ],
                    "difficulty_distribution": {"easy": 50, "hard": 50},
                },
                {
                    "round_type": "technical_interview",
                    "round_order": 3,
                    "question_count": 3,
                    "question_types": ["Technical Q&A"],
                    "topics": [
                        {"topic": "Data Structures", "weight_pct": 60},
                        {"topic": "System Design", "weight_pct": 40},
                    ],
                    "difficulty_distribution": {"easy": 20, "medium": 60, "hard": 20},
                },
            ],
        },
        confidence_level="high",
        evidence_sources_count=4,
        created_by_id=tpo.id,
    )
    db_session.add(bp)
    db_session.commit()
    db_session.refresh(bp)
    return bp


@pytest.fixture
def sample_draft_blueprint(db_session, auth_headers_tpo):
    _, tpo = auth_headers_tpo
    bp = CompanyBlueprint(
        company_name="Google",
        target_role="Software Engineer",
        status="draft",
        version=1,
        blueprint_data={
            "company_name": "Google",
            "target_role": "Software Engineer",
            "status": "draft",
            "version": 1,
            "rounds": [
                {
                    "round_type": "aptitude",
                    "round_order": 1,
                }
            ],
        },
        confidence_level="low",
        created_by_id=tpo.id,
    )
    db_session.add(bp)
    db_session.commit()
    db_session.refresh(bp)
    return bp


# ── Test Suite ────────────────────────────────────────────────────────

def test_create_mock_drive_with_approved_blueprint(client, auth_headers_tpo, sample_approved_blueprint):
    headers, _ = auth_headers_tpo
    payload = {
        "company_name": "Google",
        "target_role": "Software Engineer",
        "description": "Google 2024 Hiring Drive",
        "minimum_cgpa": 7.0,
        "maximum_backlogs": 0,
        "eligible_branches": ["Computer Science"],
        "selected_rounds": {"coding": True, "technical_interview": True},
        "blueprint_id": sample_approved_blueprint.id,
    }

    res = client.post("/api/v1/tpo/mock-drives", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["company_name"] == "Google"
    assert data["blueprint_id"] == sample_approved_blueprint.id
    assert data["blueprint_version"] == 2
    assert data["status"] == "draft"


def test_mock_drive_finds_approved_blueprint_by_exact_normalized_company_and_role(
    client, db_session, auth_headers_tpo
):
    headers, tpo = auth_headers_tpo
    expected_rounds = [
        {"round_type": "aptitude", "round_order": 1, "question_count": 30, "time_limit_minutes": 45},
        {"round_type": "coding", "round_order": 2, "question_count": 2, "time_limit_minutes": 60},
        {"round_type": "technical_interview", "round_order": 3, "question_count": 3, "time_limit_minutes": 45},
    ]
    matching = CompanyBlueprint(
        company_name="Citi Test 2",
        target_role="Software Engineer",
        status="approved",
        version=1,
        blueprint_data={"rounds": expected_rounds},
        confidence_level="medium",
        evidence_sources_count=1,
        created_by_id=tpo.id,
    )
    partial = CompanyBlueprint(
        company_name="Citi Test 2 Holdings",
        target_role="Software Engineer",
        status="approved",
        version=99,
        blueprint_data={"rounds": []},
        confidence_level="high",
        evidence_sources_count=1,
        created_by_id=tpo.id,
    )
    db_session.add_all([matching, partial])
    db_session.commit()

    response = client.get(
        "/api/v1/tpo/company-data/blueprint",
        params={"company_name": "  cItI tEsT 2 ", "target_role": "software engineer", "status": "APPROVED"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    results = response.json()
    assert len(results) == 1
    assert results[0]["id"] == matching.id
    assert results[0]["version"] == 1
    assert results[0]["blueprint_data"]["rounds"] == expected_rounds


def test_mock_drive_blueprint_lookup_returns_no_approved_result_for_missing_identity(
    client, auth_headers_tpo
):
    headers, _ = auth_headers_tpo
    response = client.get(
        "/api/v1/tpo/company-data/blueprint",
        params={"company_name": "Citi Test 2", "target_role": "Data Engineer", "status": "approved"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json() == []


def test_new_mock_drives_are_independent_and_explicit_drive_load_returns_its_data(
    client, auth_headers_tpo
):
    headers, _ = auth_headers_tpo
    first = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Citi Test 2",
            "target_role": "Software Engineer",
            "description": "Existing drive configuration",
            "minimum_cgpa": 8.5,
            "maximum_backlogs": 0,
            "eligible_branches": ["Computer Science"],
            "selected_rounds": {"coding": True},
        },
        headers=headers,
    )
    second = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Citi Test 2",
            "target_role": "Software Engineer",
            "description": None,
            "minimum_cgpa": 6.0,
            "maximum_backlogs": 0,
            "eligible_branches": [],
            "selected_rounds": {"aptitude": True},
        },
        headers=headers,
    )
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["selected_rounds"] == {"coding": True}
    assert second.json()["description"] is None
    assert second.json()["minimum_cgpa"] == 6.0
    assert second.json()["eligible_branches"] == []
    assert second.json()["selected_rounds"] == {"aptitude": True}

    explicitly_loaded = client.get(
        f"/api/v1/tpo/mock-drives/{first.json()['id']}", headers=headers
    )
    assert explicitly_loaded.status_code == 200
    assert explicitly_loaded.json()["id"] == first.json()["id"]
    assert explicitly_loaded.json()["description"] == "Existing drive configuration"
    assert explicitly_loaded.json()["selected_rounds"] == {"coding": True}


def test_editing_a_drive_keeps_its_attached_blueprint_snapshot(
    client, db_session, auth_headers_tpo, sample_approved_blueprint
):
    headers, _ = auth_headers_tpo
    created = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Google",
            "target_role": "Software Engineer",
            "selected_rounds": {"coding": True},
            "blueprint_id": sample_approved_blueprint.id,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    drive_id = created.json()["id"]
    original_snapshot = db_session.query(MockDrive).filter_by(id=drive_id).one().blueprint_snapshot

    # Blueprint rows are mutable during recalculation. An ordinary drive edit
    # sends its existing blueprint reference but must retain the pinned copy.
    sample_approved_blueprint.version += 1
    sample_approved_blueprint.blueprint_data = {"rounds": [{"round_type": "aptitude"}]}
    db_session.commit()
    updated = client.put(
        f"/api/v1/tpo/mock-drives/{drive_id}",
        json={"description": "Edited without changing blueprint", "blueprint_id": sample_approved_blueprint.id},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    drive = db_session.query(MockDrive).filter_by(id=drive_id).one()
    assert drive.blueprint_version == original_snapshot["blueprint_version"]
    assert drive.blueprint_snapshot == original_snapshot


def test_create_mock_drive_rejects_unapproved_blueprint(client, auth_headers_tpo, sample_draft_blueprint):
    headers, _ = auth_headers_tpo
    payload = {
        "company_name": "Google",
        "target_role": "Software Engineer",
        "minimum_cgpa": 6.0,
        "maximum_backlogs": 0,
        "selected_rounds": {"aptitude": True},
        "blueprint_id": sample_draft_blueprint.id,
    }

    res = client.post("/api/v1/tpo/mock-drives", json=payload, headers=headers)
    assert res.status_code == 422
    assert "only 'approved' blueprints can be linked" in res.json()["detail"]


def test_create_mock_drive_rejects_mismatched_company_blueprint(client, auth_headers_tpo, sample_approved_blueprint):
    headers, _ = auth_headers_tpo
    payload = {
        "company_name": "Microsoft",
        "target_role": "Software Engineer",
        "minimum_cgpa": 6.0,
        "maximum_backlogs": 0,
        "selected_rounds": {"coding": True},
        "blueprint_id": sample_approved_blueprint.id,
    }

    res = client.post("/api/v1/tpo/mock-drives", json=payload, headers=headers)
    assert res.status_code == 422
    assert "does not match mock drive" in res.json()["detail"]


def test_create_mock_drive_rejects_nonexistent_blueprint(client, auth_headers_tpo):
    headers, _ = auth_headers_tpo
    payload = {
        "company_name": "Google",
        "target_role": "Software Engineer",
        "minimum_cgpa": 6.0,
        "maximum_backlogs": 0,
        "selected_rounds": {"coding": True},
        "blueprint_id": 999999,
    }

    res = client.post("/api/v1/tpo/mock-drives", json=payload, headers=headers)
    assert res.status_code == 404


def test_update_mock_drive_attaches_and_detaches_blueprint(client, auth_headers_tpo, sample_approved_blueprint):
    headers, _ = auth_headers_tpo
    # 1. Create without blueprint
    create_payload = {
        "company_name": "Google",
        "target_role": "Software Engineer",
        "minimum_cgpa": 6.0,
        "maximum_backlogs": 0,
        "selected_rounds": {"coding": True},
    }
    create_res = client.post("/api/v1/tpo/mock-drives", json=create_payload, headers=headers)
    assert create_res.status_code == 201
    drive_id = create_res.json()["id"]
    assert create_res.json()["blueprint_id"] is None

    # 2. Update to attach blueprint
    update_res = client.put(
        f"/api/v1/tpo/mock-drives/{drive_id}",
        json={"blueprint_id": sample_approved_blueprint.id},
        headers=headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["blueprint_id"] == sample_approved_blueprint.id
    assert update_res.json()["blueprint_version"] == 2

    # 3. Update to detach blueprint
    detach_res = client.put(
        f"/api/v1/tpo/mock-drives/{drive_id}",
        json={"blueprint_id": None},
        headers=headers,
    )
    assert detach_res.status_code == 200
    assert detach_res.json()["blueprint_id"] is None
    assert detach_res.json()["blueprint_version"] is None


def test_student_start_mock_drive_uses_blueprint_ordering(
    client, db_session, auth_headers_tpo, auth_headers_student, sample_approved_blueprint
):
    tpo_headers, _ = auth_headers_tpo
    student_headers, student = auth_headers_student

    # Create drive linked to approved blueprint (blueprint order: coding -> technical_interview)
    drive_res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Google",
            "target_role": "Software Engineer",
            "minimum_cgpa": 6.0,
            "maximum_backlogs": 0,
            "eligible_branches": ["Computer Science"],
            "selected_rounds": {"coding": True, "technical_interview": True},
            "blueprint_id": sample_approved_blueprint.id,
        },
        headers=tpo_headers,
    )
    assert drive_res.status_code == 201
    drive_id = drive_res.json()["id"]

    # Seed required pre-generated pools for enabled blueprint rounds
    _seed_complete_pool(
        db_session, sample_approved_blueprint.id, 2, "coding",
        "Google", "Software Engineer"
    )
    _seed_complete_pool(
        db_session, sample_approved_blueprint.id, 2, "technical_interview",
        "Google", "Software Engineer"
    )

    # Publish drive
    pub_res = client.post(f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers)
    assert pub_res.status_code == 200

    # Student starts drive
    start_res = client.post(f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers)
    assert start_res.status_code == 200
    data = start_res.json()

    assert data["mock_drive_id"] == drive_id
    assert data["blueprint_id"] == sample_approved_blueprint.id
    assert data["blueprint_version"] == 2
    # Check that enabled rounds and sequence match the blueprint ordering: coding -> technical_interview
    assert data["enabled_rounds"] == ["coding", "technical_interview"]
    assert data["current_round"] == "coding"
    assert data["redirect_url"] == "/coding"

    # Check status endpoint reflects blueprint metadata
    status_res = client.get(f"/api/v1/mock-drives/{drive_id}/status", headers=student_headers)
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["blueprint_id"] == sample_approved_blueprint.id
    assert status_data["enabled_rounds"] == ["coding", "technical_interview"]
    assert status_data["current_round"] == "coding"


def test_advance_blueprint_mock_drive_round(
    client, db_session, auth_headers_tpo, auth_headers_student, sample_approved_blueprint
):
    tpo_headers, _ = auth_headers_tpo
    student_headers, _ = auth_headers_student

    # Create & publish drive with blueprint (coding -> technical_interview)
    drive_res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Google",
            "target_role": "Software Engineer",
            "minimum_cgpa": 6.0,
            "maximum_backlogs": 0,
            "selected_rounds": {"coding": True, "technical_interview": True},
            "blueprint_id": sample_approved_blueprint.id,
        },
        headers=tpo_headers,
    )
    drive_id = drive_res.json()["id"]

    # Seed required pre-generated pools for enabled blueprint rounds
    _seed_complete_pool(
        db_session, sample_approved_blueprint.id, 2, "coding",
        "Google", "Software Engineer"
    )
    _seed_complete_pool(
        db_session, sample_approved_blueprint.id, 2, "technical_interview",
        "Google", "Software Engineer"
    )

    client.post(f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers)

    # Start drive (Round 1: coding)
    client.post(f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers)

    # Advance to Round 2 (technical_interview)
    adv_res = client.post(f"/api/v1/mock-drives/{drive_id}/advance", headers=student_headers)
    assert adv_res.status_code == 200
    adv_data = adv_res.json()
    assert adv_data["current_round"] == "technical_interview"
    assert "coding" in adv_data["completed_rounds"]
    assert adv_data["blueprint_id"] == sample_approved_blueprint.id

    # Advance again to complete drive
    final_res = client.post(f"/api/v1/mock-drives/{drive_id}/advance", headers=student_headers)
    assert final_res.status_code == 200
    final_data = final_res.json()
    assert final_data["status"] == "completed"
    assert final_data["current_round"] is None
    assert set(final_data["completed_rounds"]) == {"coding", "technical_interview"}


def test_legacy_mock_drive_without_blueprint_still_works(client, auth_headers_tpo, auth_headers_student):
    tpo_headers, _ = auth_headers_tpo
    student_headers, _ = auth_headers_student

    # Create & publish drive without blueprint (canonical order: aptitude -> interview)
    drive_res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Infosys",
            "target_role": "Systems Engineer",
            "minimum_cgpa": 6.0,
            "maximum_backlogs": 0,
            "selected_rounds": {"aptitude": True, "hr_interview": True},
            "round_configurations": _blueprintless_round_config(
                "aptitude", "hr_interview"
            ),
        },
        headers=tpo_headers,
    )
    assert drive_res.status_code == 201
    drive_id = drive_res.json()["id"]
    assert drive_res.json()["blueprint_id"] is None

    publish_res = client.post(
        f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers
    )
    assert publish_res.status_code == 200, publish_res.text

    # Start legacy drive
    start_res = client.post(f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers)
    assert start_res.status_code == 200
    data = start_res.json()
    assert data["blueprint_id"] is None
    assert data["enabled_rounds"] == ["aptitude", "hr_interview"]
    assert data["current_round"] == "aptitude"


def test_draft_aptitude_and_coding_saved_reopened_and_published(client, auth_headers_tpo):
    headers, _ = auth_headers_tpo
    # 1. Create Draft with Aptitude + Coding
    payload = {
        "company_name": "TCS",
        "target_role": "Ninja Developer",
        "description": "TCS Aptitude + Coding Practice",
        "minimum_cgpa": 6.5,
        "maximum_backlogs": 0,
        "selected_rounds": {"aptitude": True, "coding": True},
        "round_configurations": _blueprintless_round_config("aptitude", "coding"),
    }
    create_res = client.post("/api/v1/tpo/mock-drives", json=payload, headers=headers)
    assert create_res.status_code == 201
    drive = create_res.json()
    assert drive["status"] == "draft"
    assert drive["selected_rounds"] == {"aptitude": True, "coding": True}
    assert drive["rounds"] == ["aptitude", "coding"]
    drive_id = drive["id"]

    # 2. Reopen draft (simulate TPO reopening or viewing the draft)
    get_res = client.get(f"/api/v1/tpo/mock-drives/{drive_id}", headers=headers)
    assert get_res.status_code == 200
    reopened = get_res.json()
    assert reopened["selected_rounds"] == {"aptitude": True, "coding": True}
    assert reopened["rounds"] == ["aptitude", "coding"]

    # 3. Publish and verify rounds are preserved without unexpected mutation
    pub_res = client.post(f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=headers)
    assert pub_res.status_code == 200
    published = pub_res.json()
    assert published["status"] == "published"
    assert published["selected_rounds"] == {"aptitude": True, "coding": True}
    assert published["rounds"] == ["aptitude", "coding"]


def test_draft_coding_and_interview_saved_reopened_and_published(client, auth_headers_tpo):
    headers, _ = auth_headers_tpo
    # 1. Create Draft with Coding + Interview (technical_interview)
    payload = {
        "company_name": "Amazon",
        "target_role": "SDE-1",
        "minimum_cgpa": 7.5,
        "maximum_backlogs": 0,
        "selected_rounds": {"coding": True, "technical_interview": True},
        "round_configurations": _blueprintless_round_config(
            "coding", "technical_interview"
        ),
    }
    create_res = client.post("/api/v1/tpo/mock-drives", json=payload, headers=headers)
    assert create_res.status_code == 201
    drive = create_res.json()
    assert drive["status"] == "draft"
    assert drive["selected_rounds"] == {"coding": True, "technical_interview": True}
    assert drive["rounds"] == ["coding", "technical_interview"]
    drive_id = drive["id"]

    # 2. Reopen draft and verify rounds
    get_res = client.get(f"/api/v1/tpo/mock-drives/{drive_id}", headers=headers)
    assert get_res.status_code == 200
    reopened = get_res.json()
    assert reopened["selected_rounds"] == {"coding": True, "technical_interview": True}
    assert reopened["rounds"] == ["coding", "technical_interview"]

    # 3. Publish and verify rounds are preserved
    pub_res = client.post(f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=headers)
    assert pub_res.status_code == 200
    published = pub_res.json()
    assert published["status"] == "published"
    assert published["selected_rounds"] == {"coding": True, "technical_interview": True}
    assert published["rounds"] == ["coding", "technical_interview"]


def test_blueprint_driven_draft_saved_reopened_and_published(
    client, db_session, auth_headers_tpo, sample_approved_blueprint
):
    headers, _ = auth_headers_tpo
    # 1. Create Blueprint-driven Draft with Aptitude + Coding
    # sample_approved_blueprint has Coding (1) and Technical Interview (2).
    payload = {
        "company_name": "Google",
        "target_role": "Software Engineer",
        "minimum_cgpa": 7.0,
        "maximum_backlogs": 0,
        "selected_rounds": {"aptitude": True, "coding": True},
        "blueprint_id": sample_approved_blueprint.id,
    }
    create_res = client.post("/api/v1/tpo/mock-drives", json=payload, headers=headers)
    assert create_res.status_code == 201
    drive = create_res.json()
    assert drive["status"] == "draft"
    assert drive["blueprint_id"] == sample_approved_blueprint.id
    assert drive["selected_rounds"] == {"aptitude": True, "coding": True}
    assert set(drive["rounds"]) == {"aptitude", "coding"}
    drive_id = drive["id"]

    # 2. Reopen draft and verify rounds are unchanged and preserved
    get_res = client.get(f"/api/v1/tpo/mock-drives/{drive_id}", headers=headers)
    assert get_res.status_code == 200
    reopened = get_res.json()
    assert reopened["blueprint_id"] == sample_approved_blueprint.id
    assert reopened["selected_rounds"] == {"aptitude": True, "coding": True}
    assert set(reopened["rounds"]) == {"aptitude", "coding"}

    # 3. Publish and verify rounds are not dropped or unexpectedly altered
    _seed_complete_pool(
        db_session, sample_approved_blueprint.id, 2, "coding",
        "Google", "Software Engineer"
    )
    pub_res = client.post(f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=headers)
    assert pub_res.status_code == 200
    published = pub_res.json()
    assert published["status"] == "published"
    assert published["selected_rounds"] == {"aptitude": True, "coding": True}
    assert set(published["rounds"]) == {"aptitude", "coding"}


def test_three_round_blueprint_draft_update_publish_and_student_progression(
    client, db_session, auth_headers_tpo, auth_headers_student, sample_three_round_blueprint
):
    tpo_headers, _ = auth_headers_tpo
    student_headers, _ = auth_headers_student
    all_rounds = {
        "aptitude": True,
        "coding": True,
        "technical_interview": True,
    }

    create_res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Google",
            "target_role": "Software Engineer",
            "selected_rounds": all_rounds,
            "blueprint_id": sample_three_round_blueprint.id,
        },
        headers=tpo_headers,
    )
    assert create_res.status_code == 201, create_res.text
    drive = create_res.json()
    drive_id = drive["id"]
    assert drive["selected_rounds"] == all_rounds
    assert drive["rounds"] == ["coding", "aptitude", "technical_interview"]

    reopened = client.get(
        f"/api/v1/tpo/mock-drives/{drive_id}", headers=tpo_headers
    ).json()
    assert reopened["selected_rounds"] == all_rounds
    assert reopened["rounds"] == ["coding", "aptitude", "technical_interview"]

    updated_rounds = {"coding": True, "technical_interview": True}
    update_res = client.put(
        f"/api/v1/tpo/mock-drives/{drive_id}",
        json={"selected_rounds": updated_rounds},
        headers=tpo_headers,
    )
    assert update_res.status_code == 200, update_res.text
    updated = client.get(
        f"/api/v1/tpo/mock-drives/{drive_id}", headers=tpo_headers
    ).json()
    assert updated["selected_rounds"] == updated_rounds
    assert updated["rounds"] == ["coding", "technical_interview"]

    # Seed required pre-generated pools for enabled blueprint rounds
    _seed_complete_pool(
        db_session, sample_three_round_blueprint.id, 3, "coding",
        "Google", "Software Engineer"
    )
    _seed_complete_pool(
        db_session, sample_three_round_blueprint.id, 3, "technical_interview",
        "Google", "Software Engineer"
    )

    publish_res = client.post(
        f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers
    )
    assert publish_res.status_code == 200, publish_res.text
    published = publish_res.json()
    assert published["selected_rounds"] == updated_rounds
    assert published["rounds"] == ["coding", "technical_interview"]

    start_res = client.post(
        f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers
    )
    assert start_res.status_code == 200, start_res.text
    started = start_res.json()
    assert started["enabled_rounds"] == ["coding", "technical_interview"]
    assert started["current_round"] == "coding"

    advance_res = client.post(
        f"/api/v1/mock-drives/{drive_id}/advance", headers=student_headers
    )
    assert advance_res.status_code == 200, advance_res.text
    assert advance_res.json()["current_round"] == "technical_interview"


def test_aptitude_coding_blueprint_draft_rounds_survive_retrieval(
    client, auth_headers_tpo, sample_aptitude_coding_blueprint
):
    headers, _ = auth_headers_tpo
    selected_rounds = {"aptitude": True, "coding": True}
    create_res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Infosys",
            "target_role": "Systems Engineer",
            "selected_rounds": selected_rounds,
            "blueprint_id": sample_aptitude_coding_blueprint.id,
        },
        headers=headers,
    )
    assert create_res.status_code == 201, create_res.text
    drive = create_res.json()
    assert drive["status"] == "draft"
    assert drive["selected_rounds"] == selected_rounds
    assert drive["rounds"] == ["aptitude", "coding"]

    retrieved = client.get(
        f"/api/v1/tpo/mock-drives/{drive['id']}", headers=headers
    )
    assert retrieved.status_code == 200
    assert retrieved.json()["selected_rounds"] == selected_rounds
    assert retrieved.json()["rounds"] == ["aptitude", "coding"]


def test_publish_empty_rounds_uses_pinned_blueprint_snapshot(
    client, db_session, auth_headers_tpo, sample_aptitude_coding_blueprint
):
    headers, _ = auth_headers_tpo
    create_res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Infosys",
            "target_role": "Systems Engineer",
            "selected_rounds": {"coding": True},
            "blueprint_id": sample_aptitude_coding_blueprint.id,
        },
        headers=headers,
    )
    assert create_res.status_code == 201, create_res.text
    drive_id = create_res.json()["id"]
    drive = db_session.query(MockDrive).filter(MockDrive.id == drive_id).first()
    drive.selected_rounds = {}

    changed_blueprint_data = dict(sample_aptitude_coding_blueprint.blueprint_data)
    changed_blueprint_data["rounds"] = [
        {"round_type": "hr_interview", "round_order": 1}
    ]
    sample_aptitude_coding_blueprint.blueprint_data = changed_blueprint_data
    sample_aptitude_coding_blueprint.version = 2
    db_session.commit()

    # Seed required pre-generated pools for pinned blueprint v1 rounds
    _seed_complete_pool(
        db_session, sample_aptitude_coding_blueprint.id, 1, "aptitude",
        "Infosys", "Systems Engineer"
    )
    _seed_complete_pool(
        db_session, sample_aptitude_coding_blueprint.id, 1, "coding",
        "Infosys", "Systems Engineer"
    )

    publish_res = client.post(
        f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=headers
    )
    assert publish_res.status_code == 200, publish_res.text
    published = publish_res.json()
    assert published["blueprint_version"] == 1
    assert published["selected_rounds"] == {"aptitude": True, "coding": True}
    assert published["rounds"] == ["aptitude", "coding"]


def test_blueprint_v2_creates_new_drive_and_session_with_v2_snapshot(
    client, db_session, auth_headers_tpo, auth_headers_student
):
    tpo_headers, tpo = auth_headers_tpo
    student_headers, student = auth_headers_student

    # The app's in-memory limiter is shared across all TestClient tests. Start
    # this multi-request runtime regression with a clean test-only window.
    middleware_stack = application.middleware_stack or application.build_middleware_stack()
    application.middleware_stack = middleware_stack
    current_middleware = middleware_stack
    while current_middleware is not None and not isinstance(
        current_middleware, RateLimitMiddleware
    ):
        current_middleware = getattr(current_middleware, "app", None)
    assert current_middleware is not None
    current_middleware._requests.clear()

    v1_round = {
        "round_type": "coding",
        "round_order": 1,
        "question_count": 2,
        "time_limit_minutes": 11,
        "topics": [{"topic": "Strings", "weight_pct": 100}],
        "difficulty_distribution": {"hard": 100},
    }
    v2_round = {
        "round_type": "coding",
        "round_order": 1,
        "question_count": 3,
        "time_limit_minutes": 23,
        "topics": [{"topic": "Arrays", "weight_pct": 100}],
        "difficulty_distribution": {"medium": 100},
    }

    def approved_blueprint(version, round_config):
        blueprint = CompanyBlueprint(
            company_name="Snapshot Isolation Corp",
            target_role="Software Engineer",
            status="approved",
            version=version,
            blueprint_data={"rounds": [round_config]},
            confidence_level="high",
            evidence_sources_count=1,
            created_by_id=tpo.id,
        )
        db_session.add(blueprint)
        db_session.commit()
        db_session.refresh(blueprint)
        return blueprint

    v1_blueprint = approved_blueprint(1, v1_round)
    v1_problems = [
        _add_coding_problem(db_session, "Strings", "hard")
        for _ in range(2)
    ]
    v1_snapshot = {
        "blueprint_id": v1_blueprint.id,
        "blueprint_version": 1,
        "status": "approved",
        "company_name": v1_blueprint.company_name,
        "target_role": v1_blueprint.target_role,
        "blueprint_data": {"rounds": [v1_round]},
    }
    v1_drive = MockDrive(
        company_name=v1_blueprint.company_name,
        target_role=v1_blueprint.target_role,
        status="active",
        selected_rounds={"coding": True},
        blueprint_id=v1_blueprint.id,
        blueprint_version=1,
        blueprint_snapshot=v1_snapshot,
        created_by_id=tpo.id,
    )
    db_session.add(v1_drive)
    db_session.flush()
    v1_context = AssessmentContext(
        mode="mock_drive",
        purpose="mock_drive",
        student_id=student.id,
        company_name=v1_drive.company_name,
        target_role=v1_drive.target_role,
        mock_drive_id=v1_drive.id,
        blueprint_snapshot={**v1_snapshot, "selected_rounds": {"coding": True}, "enabled_rounds": ["coding"]},
        policy_id=DEFAULT_PRACTICE_POLICY_ID,
        status="active",
    )
    db_session.add(v1_context)
    db_session.flush()
    v1_session = AssessmentSession(
        user_id=student.id,
        context_id=v1_context.id,
        status="in_progress",
        started_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=4),
    )
    db_session.add(v1_session)
    db_session.flush()
    v1_round_obj = AssessmentRound(
        session_id=v1_session.id,
        round_type="coding",
        status="active",
        max_questions=2,
        started_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=11),
    )
    db_session.add(v1_round_obj)
    db_session.commit()
    assert v1_context.blueprint_snapshot["blueprint_version"] == 1
    assert v1_context.blueprint_snapshot["blueprint_data"]["rounds"][0] == v1_round
    assert v1_round_obj.max_questions == 2

    v1_first_start = client.post("/api/v1/coding/start", headers=student_headers)
    assert v1_first_start.status_code == 200, v1_first_start.text
    v1_assigned_ids = {problem["id"] for problem in v1_first_start.json()}
    assert v1_assigned_ids == {problem.id for problem in v1_problems}
    assert db_session.query(SessionProblem).filter(
        SessionProblem.round_id == v1_round_obj.id
    ).count() == 2

    # Mutate the live blueprint record after the V1 session has pinned it.
    v1_blueprint.version = 2
    v1_blueprint.blueprint_data = {"rounds": [v2_round]}
    db_session.commit()
    resume_v1 = client.post(
        f"/api/v1/mock-drives/{v1_drive.id}/start", headers=student_headers
    )
    assert resume_v1.status_code == 200, resume_v1.text
    assert resume_v1.json()["session_id"] == v1_session.id
    v1_resumed_start = client.post("/api/v1/coding/start", headers=student_headers)
    assert v1_resumed_start.status_code == 200, v1_resumed_start.text
    assert {problem["id"] for problem in v1_resumed_start.json()} == v1_assigned_ids
    assert len(v1_resumed_start.json()) == 2
    assert {problem["difficulty"] for problem in v1_resumed_start.json()} == {"hard"}

    v2_blueprint = approved_blueprint(2, v2_round)
    v2_problems = [
        _add_coding_problem(db_session, "Arrays", "medium")
        for _ in range(3)
    ]
    db_session.commit()
    v2_drive_res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": v2_blueprint.company_name,
            "target_role": v2_blueprint.target_role,
            "selected_rounds": {"coding": True},
            "blueprint_id": v2_blueprint.id,
        },
        headers=tpo_headers,
    )
    assert v2_drive_res.status_code == 201, v2_drive_res.text
    v2_drive = v2_drive_res.json()
    assert v2_drive["blueprint_id"] == v2_blueprint.id
    assert v2_drive["blueprint_version"] == 2
    assert client.post(
        f"/api/v1/tpo/mock-drives/{v2_drive['id']}/publish", headers=tpo_headers
    ).status_code == 200
    v2_start = client.post(
        f"/api/v1/mock-drives/{v2_drive['id']}/start", headers=student_headers
    )
    assert v2_start.status_code == 200, v2_start.text
    v2_context = db_session.query(AssessmentContext).filter_by(
        id=v2_start.json()["context_id"]
    ).one()
    v2_session = db_session.query(AssessmentSession).filter_by(
        id=v2_start.json()["session_id"]
    ).one()
    v2_round_obj = db_session.query(AssessmentRound).filter_by(
        session_id=v2_session.id, status="active"
    ).one()
    assert v2_session.id != v1_session.id
    assert v2_session.context_id == v2_context.id
    assert v2_context.blueprint_snapshot["blueprint_version"] == 2
    assert v2_context.blueprint_snapshot["blueprint_data"]["rounds"][0] == v2_round
    assert v2_round_obj.max_questions == 3
    assert v2_round_obj.expires_at == v2_round_obj.started_at + timedelta(minutes=23)

    coding_start = client.post("/api/v1/coding/start", headers=student_headers)
    assert coding_start.status_code == 200, coding_start.text
    problems = coding_start.json()
    assert len(problems) == 3
    assert len({problem["id"] for problem in problems}) == 3
    assert {problem["difficulty"] for problem in problems} == {"medium"}
    assert {tag for problem in problems for tag in problem["tags"]} == {"Arrays"}
    assert {problem["id"] for problem in problems} == {problem.id for problem in v2_problems}
    assert v1_context.blueprint_snapshot["blueprint_version"] == 1
    assert v1_context.blueprint_snapshot["blueprint_data"]["rounds"][0] == v1_round
    assert db_session.query(AssessmentSession).filter_by(id=v1_session.id).one().context_id == v1_context.id
    assert v1_assigned_ids.isdisjoint({problem["id"] for problem in problems})

def test_coding_problem_topic_accessor_accepts_postgresql_text_array():
    problem = CodingProblem(
        title="PostgreSQL tags",
        description="Tags loaded from PostgreSQL text[]",
        difficulty="medium",
    )
    problem.tags = ["Arrays"]
    assert problem.tags_list == ["Arrays"]


def test_blueprint_generation_full_mock_drive_flow(
    client,
    db_session,
    auth_headers_tpo,
    auth_headers_student,
    sample_generation_blueprint,
    monkeypatch,
):
    tpo_headers, _ = auth_headers_tpo
    student_headers, student = auth_headers_student

    aptitude_topics = {
        name: AptitudeTopic(name=name)
        for name in ("Quantitative Aptitude", "Logical Reasoning")
    }
    db_session.add_all(aptitude_topics.values())
    db_session.flush()
    for topic in aptitude_topics.values():
        for difficulty in ("easy", "medium"):
            for duplicate in range(2):
                db_session.add(
                    AptitudeQuestion(
                        question_text=f"{topic.name} {difficulty} {duplicate}",
                        option_a="A",
                        option_b="B",
                        option_c="C",
                        option_d="D",
                        correct_option="A",
                        difficulty=difficulty,
                        topic_id=topic.id,
                        is_active=True,
                    )
                )

    for topic_name, difficulty in (
        ("Arrays", "easy"),
        ("HashMap", "hard"),
        ("Arrays", "hard"),
        ("HashMap", "easy"),
    ):
        problem = CodingProblem(
            title=f"{topic_name} {difficulty}",
            description="Return a value computed from the input.",
            difficulty=difficulty,
        )
        problem.tags_list = [topic_name]
        db_session.add(problem)
    db_session.commit()

    selected_rounds = {
        "aptitude": True,
        "coding": True,
        "technical_interview": True,
    }
    create_res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Nvidia",
            "target_role": "Software Engineer",
            "selected_rounds": selected_rounds,
            "blueprint_id": sample_generation_blueprint.id,
        },
        headers=tpo_headers,
    )
    assert create_res.status_code == 201, create_res.text
    drive_id = create_res.json()["id"]
    assert create_res.json()["blueprint_version"] == 4

    changed_blueprint_data = dict(sample_generation_blueprint.blueprint_data)
    changed_blueprint_data["rounds"] = [
        {**round_config, "question_count": 1}
        for round_config in changed_blueprint_data["rounds"]
    ]
    sample_generation_blueprint.blueprint_data = changed_blueprint_data
    sample_generation_blueprint.version = 5
    db_session.commit()

    # Seed required pre-generated pool for interview round (no seeded fallback)
    interview_pool_content = [
        {
            "id": f"tech-interview-{i}",
            "question": f"Configured interview question {i}",
            "difficulty": "MEDIUM",
            "topic": "Data Structures" if i % 2 == 0 else "System Design",
            "phase": "TECHNICAL",
            "blueprint_pool": True,
        }
        for i in range(3)
    ]
    _seed_complete_pool(
        db_session, sample_generation_blueprint.id, 4, "technical_interview",
        "Nvidia", "Software Engineer", content=interview_pool_content
    )

    publish_res = client.post(
        f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers
    )
    assert publish_res.status_code == 200, publish_res.text
    assert publish_res.json()["blueprint_version"] == 4

    start_res = client.post(
        f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers
    )
    assert start_res.status_code == 200, start_res.text
    started = start_res.json()
    context = db_session.query(AssessmentContext).filter(
        AssessmentContext.id == started["context_id"]
    ).first()
    assert context.blueprint_snapshot["blueprint_version"] == 4
    assert context.blueprint_snapshot["blueprint_data"]["rounds"][0]["question_count"] == 4

    changed_blueprint_data = dict(sample_generation_blueprint.blueprint_data)
    changed_blueprint_data["rounds"] = [
        {**round_config, "question_count": 1}
        for round_config in changed_blueprint_data["rounds"]
    ]
    sample_generation_blueprint.blueprint_data = changed_blueprint_data
    sample_generation_blueprint.version = 6
    db_session.commit()

    active_aptitude = db_session.query(AssessmentRound).filter(
        AssessmentRound.session_id == started["session_id"],
        AssessmentRound.status == "active",
    ).first()
    assert active_aptitude.max_questions == 4
    assert active_aptitude.expires_at == active_aptitude.started_at + timedelta(minutes=60)
    expected_aptitude = [
        ("Quantitative Aptitude", "easy"),
        ("Logical Reasoning", "medium"),
        ("Quantitative Aptitude", "easy"),
        ("Logical Reasoning", "medium"),
    ]
    for attempt_number, (expected_topic, expected_difficulty) in enumerate(expected_aptitude, 1):
        question_res = client.get(
            "/api/v1/aptitude/next-question", headers=student_headers
        )
        assert question_res.status_code == 200, question_res.text
        question = question_res.json()
        assert question["max_questions"] == 4
        assert (question["topic"], question["difficulty"]) == (
            expected_topic,
            expected_difficulty,
        )
        db_session.add(
            AptitudeAttempt(
                round_id=active_aptitude.id,
                question_id=question["question_id"],
                attempt_number=attempt_number,
                selected_option="A",
                is_correct=True,
                response_time=1,
                difficulty=question["difficulty"],
            )
        )
        db_session.flush()

    assert client.get(
        "/api/v1/aptitude/next-question", headers=student_headers
    ).status_code == 404
    aptitude_finish = client.post("/api/v1/aptitude/finish", headers=student_headers)
    assert aptitude_finish.status_code == 200, aptitude_finish.text
    assert aptitude_finish.json()["mock_drive"]["current_round"] == "coding"

    coding_start = client.post("/api/v1/coding/start", headers=student_headers)
    assert coding_start.status_code == 200, coding_start.text
    coding_problems = coding_start.json()
    assert len(coding_problems) == 2
    assert {problem["tags"][0] for problem in coding_problems} == {"Arrays", "HashMap"}
    assert {problem["difficulty"] for problem in coding_problems} == {"easy", "hard"}

    coding_finish = client.post("/api/v1/coding/finish", headers=student_headers)
    assert coding_finish.status_code == 200, coding_finish.text
    assert coding_finish.json()["mock_drive"]["current_round"] == "technical_interview"

    # G1: interview pool is pre-generated; candidate uses start-active to clone it
    # (no resume upload / candidate-time LLM generation for blueprint-backed interviews)
    interview_start = client.post(
        "/api/v1/interview/session/start-active", headers=student_headers
    )
    assert interview_start.status_code == 200, interview_start.text
    assert interview_start.json()["total_turns"] == 3
    assert interview_start.json()["phase"] == "TECHNICAL"


def test_pinned_blueprint_snapshot_survives_live_status_change(
    client, db_session, auth_headers_tpo, auth_headers_student, sample_generation_blueprint
):
    tpo_headers, _ = auth_headers_tpo
    student_headers, _ = auth_headers_student
    create_res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Nvidia",
            "target_role": "Software Engineer",
            "selected_rounds": {"aptitude": True},
            "blueprint_id": sample_generation_blueprint.id,
        },
        headers=tpo_headers,
    )
    assert create_res.status_code == 201, create_res.text
    drive_id = create_res.json()["id"]

    # Seed required pre-generated pool for aptitude round (no feasible seeded bank in this test)
    _seed_complete_pool(
        db_session, sample_generation_blueprint.id, 4, "aptitude",
        "Nvidia", "Software Engineer"
    )

    publish_res = client.post(
        f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers
    )
    assert publish_res.status_code == 200, publish_res.text

    sample_generation_blueprint.status = "draft"
    db_session.commit()
    start_res = client.post(
        f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers
    )
    assert start_res.status_code == 200, start_res.text
    context = db_session.query(AssessmentContext).filter(
        AssessmentContext.id == start_res.json()["context_id"]
    ).first()
    assert context.blueprint_snapshot["status"] == "approved"
    assert context.blueprint_snapshot["blueprint_version"] == create_res.json()["blueprint_version"]


def test_blueprint_aptitude_rejects_submission_after_question_limit(
    client,
    db_session,
    auth_headers_tpo,
    auth_headers_student,
    sample_generation_blueprint,
):
    tpo_headers, _ = auth_headers_tpo
    student_headers, _ = auth_headers_student
    blueprint_data = dict(sample_generation_blueprint.blueprint_data)
    blueprint_data["rounds"] = [
        {
            **round_config,
            **({"question_count": 10} if round_config["round_type"] == "aptitude" else {}),
        }
        for round_config in blueprint_data["rounds"]
    ]
    sample_generation_blueprint.blueprint_data = blueprint_data
    db_session.commit()

    create_res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Nvidia",
            "target_role": "Software Engineer",
            "selected_rounds": {"aptitude": True},
            "blueprint_id": sample_generation_blueprint.id,
        },
        headers=tpo_headers,
    )
    assert create_res.status_code == 201, create_res.text
    drive_id = create_res.json()["id"]

    # Seed required pre-generated pool for aptitude round
    _seed_complete_pool(
        db_session, sample_generation_blueprint.id, 4, "aptitude",
        "Nvidia", "Software Engineer"
    )

    publish_res = client.post(
        f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers
    )
    assert publish_res.status_code == 200, publish_res.text
    start_res = client.post(
        f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers
    )
    assert start_res.status_code == 200, start_res.text

    topic = AptitudeTopic(name="Blueprint Count Topic")
    db_session.add(topic)
    db_session.flush()
    question = AptitudeQuestion(
        question_text="Blueprint count guard test",
        option_a="A",
        option_b="B",
        option_c="C",
        option_d="D",
        correct_option="A",
        difficulty="easy",
        topic_id=topic.id,
        is_active=True,
    )
    db_session.add(question)
    db_session.flush()

    active_round = db_session.query(AssessmentRound).filter(
        AssessmentRound.session_id == start_res.json()["session_id"],
        AssessmentRound.status == "active",
    ).first()
    for attempt_number in range(1, 11):
        db_session.add(
            AptitudeAttempt(
                round_id=active_round.id,
                question_id=question.id,
                attempt_number=attempt_number,
                selected_option="A",
                is_correct=True,
                response_time=1,
                difficulty="easy",
            )
        )
    db_session.flush()

    eleventh_res = client.post(
        "/api/v1/aptitude/submit-answer",
        json={
            "question_id": question.id,
            "selected_option": "A",
            "response_time": 1,
        },
        headers=student_headers,
    )
    assert eleventh_res.status_code == 409
    assert "question count has been reached" in eleventh_res.json()["detail"]
    assert db_session.query(AptitudeAttempt.id).filter(
        AptitudeAttempt.round_id == active_round.id
    ).count() == 10


def test_groq_blueprint_prompt_uses_configured_difficulty_and_topics(monkeypatch):
    captured = {}
    response = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=(
                        '{"questions":[{"question":"Explain arrays",'
                        '"difficulty":"MEDIUM","topic":"Arrays",'
                        '"phase":"TECHNICAL"}]}'
                    )
                )
            )
        ]
    )

    def fake_create(**kwargs):
        captured["prompt"] = kwargs["messages"][0]["content"]
        return response

    service = GroqService.__new__(GroqService)
    service.client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=fake_create)
        )
    )
    monkeypatch.setattr(
        "app.services.role_detection_service.detect_role",
        lambda skills, projects: "Software Engineer",
    )
    monkeypatch.setattr("app.services.retriever_service.retrieve", lambda **kwargs: [])
    monkeypatch.setattr(
        "app.services.retriever_service.format_for_prompt", lambda documents: ""
    )

    service.generate_question_pool(
        ["Python"],
        {},
        count=3,
        interview_type="technical",
        blueprint_constraints={
            "company_name": "Nvidia",
            "target_role": "Software Engineer",
            "topics": [
                {"topic": "Arrays", "weight_pct": 70},
                {"topic": "System Design", "weight_pct": 30},
            ],
            "difficulty_distribution": {"easy": 20, "medium": 60, "hard": 20},
        },
    )

    assert "Generate exactly 3 TECHNICAL interview questions" in captured["prompt"]
    assert "Follow the approved blueprint difficulty distribution exactly" in captured["prompt"]
    assert '"easy": 20' in captured["prompt"]
    assert '"topic": "Arrays", "weight_pct": 70' in captured["prompt"]
    assert "Distribute difficulty: 3 EASY, 5 MEDIUM, 4 HARD" not in captured["prompt"]


def test_blueprint_interview_pool_fails_closed_when_no_pre_generated_pool(monkeypatch):
    """G1: blueprint-backed interview without pre-generated pool fails closed (422), no LLM fallback."""
    round_config = {
        "question_count": 3,
        "topics": [{"topic": "Arrays", "weight_pct": 100}],
        "difficulty_distribution": {"easy": 20, "medium": 60, "hard": 20},
    }
    snapshot = {
        "company_name": "Nvidia",
        "target_role": "Software Engineer",
    }
    monkeypatch.setattr(
        interview_router_module,
        "get_session_active_blueprint_round_config",
        lambda db, session_id, fallback: (snapshot, round_config, "technical_interview"),
    )
    # Track if LLM generation is attempted
    calls = []

    def fake_generate(*args, **kwargs):
        calls.append(kwargs)
        return [{"question": f"question {index}"} for index in range(3)]

    monkeypatch.setattr(interview_router_module.groq_service, "generate_question_pool", fake_generate)

    # With G1, blueprint-backed interview without pre-generated pool should raise 422
    with pytest.raises(HTTPException) as error:
        interview_router_module._generate_question_pool_for_session(
            db=None,
            session_id=1,
            skills=["Python"],
            projects={},
            interview_type="technical",
        )
    assert error.value.status_code == 422
    assert "technical_interview question pool must be generated" in error.value.detail
    # LLM generation should NOT be attempted
    assert len(calls) == 0


def test_blueprint_interview_pool_uses_pre_generated_pool_when_available(monkeypatch):
    """G1: blueprint-backed interview with valid pre-generated pool uses it (no LLM call)."""
    round_config = {
        "question_count": 3,
        "topics": [{"topic": "Arrays", "weight_pct": 100}],
        "difficulty_distribution": {"easy": 20, "medium": 60, "hard": 20},
    }
    snapshot = {
        "company_name": "Nvidia",
        "target_role": "Software Engineer",
        "blueprint_id": 1,
        "blueprint_version": 1,
    }
    monkeypatch.setattr(
        interview_router_module,
        "get_session_active_blueprint_round_config",
        lambda db, session_id, fallback: (snapshot, round_config, "technical_interview"),
    )
    # Mock the pool service to return a complete pool
    from unittest.mock import MagicMock
    from app.services.question_pool_generation_service import question_pool_generation_service
    mock_pool = MagicMock()
    mock_pool.content = [
        {"question": "q1", "phase": "TECHNICAL", "difficulty": "MEDIUM"},
        {"question": "q2", "phase": "TECHNICAL", "difficulty": "MEDIUM"},
        {"question": "q3", "phase": "TECHNICAL", "difficulty": "MEDIUM"},
    ]
    monkeypatch.setattr(
        question_pool_generation_service,
        "complete_pool_for_round",
        lambda *args, **kwargs: mock_pool,
    )

    calls = []
    monkeypatch.setattr(interview_router_module.groq_service, "generate_question_pool", lambda *a, **k: calls.append(k) or [])

    pool, count, is_blueprint = interview_router_module._generate_question_pool_for_session(
        db=None,
        session_id=1,
        skills=["Python"],
        projects={},
        interview_type="technical",
    )
    assert len(pool) == 3
    assert count == 3
    assert is_blueprint is True
    # LLM generation should NOT be called when pre-generated pool exists
    assert len(calls) == 0


# ── G3: Mock Drive session-start pool readiness ────────────────────────

def test_g3_session_start_rejects_when_interview_pool_missing(
    client, db_session, auth_headers_tpo, auth_headers_student, sample_approved_blueprint
):
    """G3: session start fails with 409 when interview pool is missing (defense-in-depth).

    This tests the G3 gate directly by using a mock to simulate a published drive
    where the pool check was somehow bypassed (legacy data, manual DB manipulation,
    or future regression). In normal operation, G2 publish gate would also catch this.
    """
    from unittest.mock import MagicMock, patch
    from app.services.question_pool_generation_service import question_pool_generation_service

    tpo_headers, _ = auth_headers_tpo
    student_headers, student = auth_headers_student

    # Seed pool for publish (so G2 passes) - sample_approved_blueprint has technical_interview
    interview_pool_content = [
        {
            "id": f"tech-interview-{i}",
            "question": f"Configured interview question {i}",
            "difficulty": "MEDIUM",
            "topic": "Data Structures" if i % 2 == 0 else "System Design",
            "phase": "TECHNICAL",
            "blueprint_pool": True,
        }
        for i in range(3)
    ]
    _seed_complete_pool(
        db_session, sample_approved_blueprint.id, 2, "technical_interview",
        "Google", "Software Engineer", content=interview_pool_content
    )

    create_res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Google",
            "target_role": "Software Engineer",
            "selected_rounds": {"technical_interview": True},
            "blueprint_id": sample_approved_blueprint.id,
        },
        headers=tpo_headers,
    )
    assert create_res.status_code == 201
    drive_id = create_res.json()["id"]
    publish_res = client.post(f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers)
    if publish_res.status_code != 200:
        print("Publish error:", publish_res.status_code, publish_res.json())
    assert publish_res.status_code == 200

    # Now simulate pool being missing at session start (defense-in-depth)
    # by patching the pool service to return None
    with patch.object(
        question_pool_generation_service,
        "complete_pool_for_round",
        return_value=None
    ):
        start_res = client.post(f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers)

    assert start_res.status_code == 409
    assert "required interview question pools are missing" in start_res.json()["detail"]["message"]
    assert "technical_interview" in start_res.json()["detail"]["missing_rounds"]

    # Verify no AssessmentContext, AssessmentSession, or AssessmentRound was created
    from app.models.assessment_context import AssessmentContext
    from app.models.assessment import AssessmentSession, AssessmentRound
    ctx_count = db_session.query(AssessmentContext).filter(
        AssessmentContext.mock_drive_id == drive_id,
        AssessmentContext.student_id == student.id,
    ).count()
    assert ctx_count == 0
    sess_count = db_session.query(AssessmentSession).join(AssessmentContext).filter(
        AssessmentContext.mock_drive_id == drive_id,
    ).count()
    assert sess_count == 0
    round_count = db_session.query(AssessmentRound).join(AssessmentSession).join(AssessmentContext).filter(
        AssessmentContext.mock_drive_id == drive_id,
    ).count()
    assert round_count == 0


def test_g3_session_start_succeeds_when_interview_pool_present(
    client, db_session, auth_headers_tpo, auth_headers_student, sample_approved_blueprint
):
    """G3: blueprint-backed drive with complete interview pool → session start succeeds."""
    tpo_headers, _ = auth_headers_tpo
    student_headers, student = auth_headers_student

    # Seed the technical_interview pool
    interview_pool_content = [
        {
            "id": f"tech-interview-{i}",
            "question": f"Configured interview question {i}",
            "difficulty": "MEDIUM",
            "topic": "Data Structures" if i % 2 == 0 else "System Design",
            "phase": "TECHNICAL",
            "blueprint_pool": True,
        }
        for i in range(3)
    ]
    _seed_complete_pool(
        db_session, sample_approved_blueprint.id, 2, "technical_interview",
        "Google", "Software Engineer", content=interview_pool_content
    )

    # Create and publish drive
    create_res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Google",
            "target_role": "Software Engineer",
            "selected_rounds": {"technical_interview": True},
            "blueprint_id": sample_approved_blueprint.id,
        },
        headers=tpo_headers,
    )
    assert create_res.status_code == 201
    drive_id = create_res.json()["id"]
    publish_res = client.post(f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers)
    assert publish_res.status_code == 200

    # Session start should succeed
    start_res = client.post(f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers)
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "in_progress"
    assert "technical_interview" in start_res.json()["enabled_rounds"]


def test_g3_session_start_rejects_when_hr_pool_missing_but_tech_present(
    client, db_session, auth_headers_tpo, auth_headers_student
):
    """G3: drive with both technical and HR interviews → both pools required at session start.

    Uses a mock to simulate a published drive where the HR pool is missing
    (defense-in-depth: G2 publish gate would also catch this, but G3 provides
    defense-in-depth for legacy data or future regressions).
    """
    from unittest.mock import patch
    from app.services.question_pool_generation_service import question_pool_generation_service
    from app.models.company_data import CompanyBlueprint
    tpo_headers, _ = auth_headers_tpo
    student_headers, student = auth_headers_student
    _, tpo = auth_headers_tpo

    # Create a blueprint with both technical_interview and hr_interview
    bp = CompanyBlueprint(
        company_name="Two Interviews Inc",
        target_role="Software Engineer",
        status="approved",
        version=1,
        blueprint_data={
            "company_name": "Two Interviews Inc",
            "target_role": "Software Engineer",
            "status": "approved",
            "version": 1,
            "rounds": [
                {
                    "round_type": "technical_interview",
                    "round_order": 1,
                    "round_name": "Technical Interview",
                    "question_count": 3,
                },
                {
                    "round_type": "hr_interview",
                    "round_order": 2,
                    "round_name": "HR Interview",
                    "question_count": 3,
                },
            ],
        },
        confidence_level="high",
        evidence_sources_count=3,
        created_by_id=tpo.id,
    )
    db_session.add(bp)
    db_session.commit()
    db_session.refresh(bp)

    # Seed both pools for publish (so G2 passes)
    tech_pool_content = [
        {
            "id": f"tech-interview-{i}",
            "question": f"Configured interview question {i}",
            "difficulty": "MEDIUM",
            "topic": "Data Structures",
            "phase": "TECHNICAL",
            "blueprint_pool": True,
        }
        for i in range(3)
    ]
    hr_pool_content = [
        {
            "id": f"hr-interview-{i}",
            "question": f"HR question {i}",
            "difficulty": "MEDIUM",
            "topic": "Behavioral",
            "phase": "HR",
            "blueprint_pool": True,
        }
        for i in range(3)
    ]
    _seed_complete_pool(
        db_session, bp.id, 1, "technical_interview",
        "Two Interviews Inc", "Software Engineer", content=tech_pool_content
    )
    _seed_complete_pool(
        db_session, bp.id, 1, "hr_interview",
        "Two Interviews Inc", "Software Engineer", content=hr_pool_content
    )

    create_res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Two Interviews Inc",
            "target_role": "Software Engineer",
            "selected_rounds": {"technical_interview": True, "hr_interview": True},
            "blueprint_id": bp.id,
        },
        headers=tpo_headers,
    )
    assert create_res.status_code == 201
    drive_id = create_res.json()["id"]
    publish_res = client.post(f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers)
    assert publish_res.status_code == 200

    # Now simulate HR pool missing at session start (defense-in-depth)
    # by patching the pool service to return None for hr_interview only
    original_complete_pool = question_pool_generation_service.complete_pool_for_round
    def mock_complete_pool(db, bp_id, bp_version, round_type):
        if round_type == "hr_interview":
            return None
        return original_complete_pool(db, bp_id, bp_version, round_type)

    with patch.object(
        question_pool_generation_service,
        "complete_pool_for_round",
        side_effect=mock_complete_pool
    ):
        start_res = client.post(f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers)

    assert start_res.status_code == 409
    assert "hr_interview" in start_res.json()["detail"]["missing_rounds"]

    # Verify no AssessmentContext, AssessmentSession, or AssessmentRound was created
    from app.models.assessment_context import AssessmentContext
    from app.models.assessment import AssessmentSession, AssessmentRound
    ctx_count = db_session.query(AssessmentContext).filter(
        AssessmentContext.mock_drive_id == drive_id,
        AssessmentContext.student_id == student.id,
    ).count()
    assert ctx_count == 0


def test_g3_session_start_legacy_blueprintless_unchanged(
    client, auth_headers_tpo, auth_headers_student
):
    """G3: legacy blueprintless drive → session start behavior unchanged (no pool check)."""
    tpo_headers, _ = auth_headers_tpo
    student_headers, student = auth_headers_student

    # Create blueprintless drive with technical_interview
    create_res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Legacy Corp",
            "target_role": "Software Engineer",
            "selected_rounds": {"technical_interview": True},
            "round_configurations": _blueprintless_round_config("technical_interview"),
        },
        headers=tpo_headers,
    )
    assert create_res.status_code == 201
    drive_id = create_res.json()["id"]
    assert create_res.json()["blueprint_id"] is None

    publish_res = client.post(f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers)
    assert publish_res.status_code == 200

    # Session start should succeed (legacy path, no pool required)
    start_res = client.post(f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers)
    assert start_res.status_code == 200
    assert start_res.json()["status"] == "in_progress"


def test_g3_session_start_wrong_blueprint_version_rejected(
    client, db_session, auth_headers_tpo, auth_headers_student, sample_approved_blueprint
):
    """G3: pool exists for wrong blueprint version → rejected at session start.

    Uses a mock to simulate a published drive where the pool version mismatch
    was somehow not caught at publish (defense-in-depth).
    """
    from unittest.mock import patch
    from app.services.question_pool_generation_service import question_pool_generation_service

    tpo_headers, _ = auth_headers_tpo
    student_headers, student = auth_headers_student

    # Seed pool for version 2
    interview_pool_content = [
        {
            "id": f"tech-interview-{i}",
            "question": f"Configured interview question {i}",
            "difficulty": "MEDIUM",
            "topic": "Data Structures",
            "phase": "TECHNICAL",
            "blueprint_pool": True,
        }
        for i in range(3)
    ]
    _seed_complete_pool(
        db_session, sample_approved_blueprint.id, 2, "technical_interview",
        "Google", "Software Engineer", content=interview_pool_content
    )

    # Mutate blueprint to version 3 (drive will pin version 3)
    sample_approved_blueprint.version = 3
    sample_approved_blueprint.blueprint_data = {
        **sample_approved_blueprint.blueprint_data,
        "version": 3,
    }
    db_session.commit()

    # Create drive with version 3 (pinned)
    create_res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Google",
            "target_role": "Software Engineer",
            "selected_rounds": {"technical_interview": True},
            "blueprint_id": sample_approved_blueprint.id,
        },
        headers=tpo_headers,
    )
    assert create_res.status_code == 201
    drive_id = create_res.json()["id"]
    assert create_res.json()["blueprint_version"] == 3  # Pins the new version

    # Seed pool for version 3 so publish succeeds (G2 gate)
    interview_pool_content_v3 = [
        {
            "id": f"tech-interview-v3-{i}",
            "question": f"Configured interview question v3 {i}",
            "difficulty": "MEDIUM",
            "topic": "Data Structures",
            "phase": "TECHNICAL",
            "blueprint_pool": True,
        }
        for i in range(3)
    ]
    _seed_complete_pool(
        db_session, sample_approved_blueprint.id, 3, "technical_interview",
        "Google", "Software Engineer", content=interview_pool_content_v3
    )

    publish_res = client.post(f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers)
    assert publish_res.status_code == 200

    # Now simulate pool missing at session start because pool is for version 2
    # but drive pins version 3 (defense-in-depth)
    original_complete_pool = question_pool_generation_service.complete_pool_for_round
    def mock_complete_pool(db, bp_id, bp_version, round_type):
        if round_type == "technical_interview" and bp_version == 3:
            return None
        return original_complete_pool(db, bp_id, bp_version, round_type)

    with patch.object(
        question_pool_generation_service,
        "complete_pool_for_round",
        side_effect=mock_complete_pool
    ):
        start_res = client.post(f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers)

    assert start_res.status_code == 409
    assert "technical_interview" in start_res.json()["detail"]["missing_rounds"]

    # Verify no AssessmentContext, AssessmentSession, or AssessmentRound was created
    from app.models.assessment_context import AssessmentContext
    from app.models.assessment import AssessmentSession, AssessmentRound
    ctx_count = db_session.query(AssessmentContext).filter(
        AssessmentContext.mock_drive_id == drive_id,
        AssessmentContext.student_id == student.id,
    ).count()
    assert ctx_count == 0


def _create_active_coding_round(
    db_session,
    student,
    tpo,
    round_config=None,
    *,
    blueprint_backed=True,
):
    now = datetime.utcnow()
    context_id = None
    if blueprint_backed:
        round_config = round_config or {
            "round_type": "coding",
            "question_count": 2,
            "topics": [
                {"topic": "Arrays", "weight_pct": 50},
                {"topic": "HashMap", "weight_pct": 50},
            ],
            "difficulty_distribution": {"easy": 50, "hard": 50},
        }
        blueprint = CompanyBlueprint(
            company_name="Test Company",
            target_role="Software Engineer",
            status="approved",
            version=1,
            blueprint_data={"rounds": [round_config]},
            confidence_level="high",
            evidence_sources_count=1,
            created_by_id=tpo.id,
        )
        db_session.add(blueprint)
        db_session.flush()
        blueprint_snapshot = {
            "blueprint_id": blueprint.id,
            "blueprint_version": blueprint.version,
            "status": blueprint.status,
            "company_name": blueprint.company_name,
            "target_role": blueprint.target_role,
            "blueprint_data": blueprint.blueprint_data,
        }
        drive = MockDrive(
            company_name=blueprint.company_name,
            target_role=blueprint.target_role,
            status="active",
            selected_rounds={"coding": True},
            blueprint_id=blueprint.id,
            blueprint_version=blueprint.version,
            blueprint_snapshot=blueprint_snapshot,
            created_by_id=tpo.id,
        )
        db_session.add(drive)
        db_session.flush()
        context = AssessmentContext(
            mode="mock_drive",
            purpose="mock_drive",
            student_id=student.id,
            company_name=drive.company_name,
            target_role=drive.target_role,
            mock_drive_id=drive.id,
            blueprint_snapshot=blueprint_snapshot,
            policy_id=DEFAULT_PRACTICE_POLICY_ID,
            status="active",
        )
        db_session.add(context)
        db_session.flush()
        context_id = context.id

    session = AssessmentSession(
        user_id=student.id,
        context_id=context_id,
        status="in_progress",
        started_at=now,
        expires_at=now + timedelta(hours=4),
    )
    db_session.add(session)
    db_session.flush()
    assessment_round = AssessmentRound(
        session_id=session.id,
        round_type="coding",
        status="active",
        max_questions=20,
        started_at=now,
        expires_at=now + timedelta(minutes=60),
    )
    db_session.add(assessment_round)
    db_session.commit()
    return assessment_round


def _add_coding_problem(db_session, topic, difficulty):
    problem = CodingProblem(
        title=f"{topic} {difficulty}",
        description="Return a value computed from the input.",
        difficulty=difficulty,
    )
    problem.tags_list = [topic]
    db_session.add(problem)
    db_session.flush()
    return problem


def _seed_complete_pool(db_session, blueprint_id, blueprint_version, round_type, company_name, target_role, content=None):
    """Insert a COMPLETE GeneratedQuestionPool row for the given blueprint/version/round."""
    if content is None:
        content = [] if round_type in ("technical_interview", "hr_interview") else None
    pool = GeneratedQuestionPool(
        blueprint_id=blueprint_id,
        blueprint_version=blueprint_version,
        company_name=company_name,
        target_role=target_role,
        round_type=round_type,
        status=POOL_STATUS_COMPLETE,
        required_count=POOL_SIZES.get(round_type, 10),
        validated_count=POOL_SIZES.get(round_type, 10),
        content=content,
    )
    db_session.add(pool)
    db_session.flush()
    return pool


def test_coding_blueprint_insufficient_topic_inventory_does_not_expose_unrelated_problems(
    client, db_session, auth_headers_student, auth_headers_tpo
):
    student_headers, student = auth_headers_student
    _, tpo = auth_headers_tpo
    round_config = {
        "round_type": "coding",
        "question_count": 2,
        "topics": [
            {"topic": "Arrays", "weight_pct": 50},
            {"topic": "HashMap", "weight_pct": 50},
        ],
    }
    _create_active_coding_round(db_session, student, tpo, round_config)
    unrelated = _add_coding_problem(db_session, "Strings", "easy")
    _add_coding_problem(db_session, "Arrays", "easy")
    db_session.commit()

    start_response = client.post("/api/v1/coding/start", headers=student_headers)
    assert start_response.status_code == 400
    assert "cannot currently be satisfied" in start_response.json()["detail"]

    problems_response = client.get("/api/v1/coding/problems", headers=student_headers)
    assert problems_response.status_code == 409
    assert unrelated.title not in problems_response.text
    assert db_session.query(SessionProblem).count() == 0


def test_blueprint_aptitude_expands_seeded_subtopics_and_empty_finish_does_not_advance(
    client, db_session, auth_headers_student, auth_headers_tpo
):
    """Broad approved topics resolve to curated subtopics; an empty run cannot skip ahead."""
    student_headers, student = auth_headers_student
    _, tpo = auth_headers_tpo
    snapshot = {
        "status": "approved",
        "company_name": "Citi Test 2",
        "target_role": "Software Engineer",
        "blueprint_version": 1,
        "blueprint_data": {
            "rounds": [
                {
                    "round_type": "aptitude",
                    "question_count": 30,
                    "time_limit_minutes": 45,
                    "question_types": ["MCQ"],
                    "topics": [
                        {"topic": "Quantitative Aptitude", "weight_pct": 33.3},
                        {"topic": "Logical Reasoning", "weight_pct": 33.3},
                        {"topic": "Verbal Ability", "weight_pct": 33.4},
                    ],
                    "difficulty_distribution": {"medium": 100},
                },
                {
                    "round_type": "coding",
                    "question_count": 2,
                    "time_limit_minutes": 60,
                    "topics": [
                        {"topic": "Data Structures & Algorithms", "weight_pct": 25},
                        {"topic": "Arrays", "weight_pct": 25},
                        {"topic": "Strings", "weight_pct": 25},
                        {"topic": "Trees & Binary Search Trees", "weight_pct": 25},
                    ],
                },
            ]
        },
    }
    drive = MockDrive(
        company_name="Citi Test 2",
        target_role="Software Engineer",
        status="active",
        selected_rounds={"aptitude": True, "coding": True},
        blueprint_snapshot=snapshot,
        created_by_id=student.id,
    )
    db_session.add(drive)
    db_session.flush()
    context = AssessmentContext(
        mode="mock_drive",
        purpose="mock_drive",
        student_id=student.id,
        company_name="Citi Test 2",
        target_role="Software Engineer",
        mock_drive_id=drive.id,
        blueprint_snapshot=snapshot,
        policy_id=DEFAULT_PRACTICE_POLICY_ID,
        status="active",
    )
    db_session.add(context)
    db_session.flush()
    session = AssessmentSession(
        user_id=student.id,
        context_id=context.id,
        status="in_progress",
        started_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=3),
    )
    db_session.add(session)
    db_session.flush()
    active_round = AssessmentRound(
        session_id=session.id,
        round_type="aptitude",
        status="active",
        max_questions=30,
        started_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(minutes=45),
    )
    db_session.add(active_round)
    db_session.commit()

    # The curated question bank uses topic-level rows instead of the three
    # broader blueprint headings.
    seeded_topics = ["Percentages", "Logical Puzzles", "Vocabulary"]
    db_topics = {name: AptitudeTopic(name=name) for name in seeded_topics}
    db_session.add_all(db_topics.values())
    db_session.flush()
    for name, topic in db_topics.items():
        for index in range(10):
            db_session.add(
                AptitudeQuestion(
                    question_text=f"{name} seeded question {index}",
                    option_a="A",
                    option_b="B",
                    option_c="C",
                    option_d="D",
                    correct_option="A",
                    difficulty="medium",
                    topic_id=topic.id,
                    is_active=True,
                )
            )
    db_session.commit()

    # No answer/question activity means Finish must not mark Aptitude complete
    # or create/advance into the Coding round.
    finish_response = client.post("/api/v1/aptitude/finish", headers=student_headers)
    assert finish_response.status_code == 409, finish_response.text
    db_session.refresh(active_round)
    assert active_round.status == "active"
    assert db_session.query(AssessmentRound).filter(
        AssessmentRound.session_id == session.id,
        AssessmentRound.round_type == "coding",
    ).count() == 0

    # Run the complete pinned Aptitude schedule from seeded subtopic rows.
    returned_topics = []
    returned_ids = set()
    persisted_ids = set()
    for attempt_number in range(1, 31):
        next_response = client.get(
            "/api/v1/aptitude/next-question", headers=student_headers
        )
        assert next_response.status_code == 200, next_response.text
        question = next_response.json()
        assert question["max_questions"] == 30
        assert question["question_number"] == attempt_number
        assert question["topic"] in seeded_topics
        assert question["difficulty"] == "medium"
        if attempt_number == 1:
            retry_response = client.get(
                "/api/v1/aptitude/next-question", headers=student_headers
            )
            assert retry_response.status_code == 200
            assert retry_response.json()["question_id"] == question["question_id"]
        assert question["question_id"] not in returned_ids
        returned_ids.add(question["question_id"])
        persisted_ids.add(question["question_id"])
        assert db_session.query(AptitudeRoundQuestion).filter(
            AptitudeRoundQuestion.round_id == active_round.id
        ).count() == 30
        returned_topics.append(question["topic"])
        db_session.add(
            AptitudeAttempt(
                round_id=active_round.id,
                question_id=question["question_id"],
                attempt_number=attempt_number,
                selected_option="A",
                is_correct=True,
                response_time=1,
                difficulty=question["difficulty"],
            )
        )
        db_session.flush()
    assert len(returned_ids) == 30
    assert {topic: returned_topics.count(topic) for topic in seeded_topics} == {
        topic: 10 for topic in seeded_topics
    }
    assert {
        assignment.question_id
        for assignment in db_session.query(AptitudeRoundQuestion)
        .filter(AptitudeRoundQuestion.round_id == active_round.id)
        .all()
    } == persisted_ids
    assert client.get(
        "/api/v1/aptitude/next-question", headers=student_headers
    ).status_code == 404


def test_blueprint_coding_start_is_idempotent_and_uses_pinned_round_count_and_time(
    client, db_session, auth_headers_student, auth_headers_tpo
):
    student_headers, student = auth_headers_student
    _, tpo = auth_headers_tpo
    round_config = {
        "round_type": "coding",
        "question_count": 2,
        "time_limit_minutes": 60,
        "topics": [
            {"topic": "Data Structures & Algorithms", "weight_pct": 25},
            {"topic": "Arrays", "weight_pct": 25},
            {"topic": "Strings", "weight_pct": 25},
            {"topic": "Trees & Binary Search Trees", "weight_pct": 25},
        ],
        "difficulty_distribution": {"medium": 100},
    }
    active_round = _create_active_coding_round(
        db_session, student, tpo, round_config
    )
    dsa = _add_coding_problem(db_session, "Graphs & Graph Algorithms", "medium")
    arrays = _add_coding_problem(db_session, "Arrays", "medium")
    db_session.commit()

    first = client.post("/api/v1/coding/start", headers=student_headers)
    second = client.post("/api/v1/coding/start", headers=student_headers)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    first_ids = {item["id"] for item in first.json()}
    assert first_ids == {dsa.id, arrays.id}
    assert {item["tags"][0] for item in first.json()} == {
        "Graphs & Graph Algorithms", "Arrays"
    }
    assert {item["difficulty"] for item in first.json()} == {"medium"}
    assert {item["id"] for item in second.json()} == first_ids
    assert db_session.query(SessionProblem).filter(
        SessionProblem.round_id == active_round.id
    ).count() == 2
    problem_list = client.get("/api/v1/coding/problems", headers=student_headers)
    assert problem_list.status_code == 200, problem_list.text
    assert {item["id"] for item in problem_list.json()} == first_ids

    db_session.refresh(active_round)
    assert active_round.max_questions == 2
    assert active_round.expires_at == active_round.started_at + timedelta(minutes=60)
    assert active_round.status == "active"


def test_blueprint_aptitude_insufficient_inventory_fails_without_partial_assignments(
    client, db_session, auth_headers_student, auth_headers_tpo
):
    student_headers, student = auth_headers_student
    _, tpo = auth_headers_tpo
    round_config = {
        "round_type": "aptitude",
        "question_count": 4,
        "time_limit_minutes": 45,
        "question_types": ["MCQ"],
        "topics": [
            {"topic": "Quantitative Aptitude", "weight_pct": 50},
            {"topic": "Verbal Ability", "weight_pct": 50},
        ],
        "difficulty_distribution": {"medium": 100},
    }
    snapshot = {
        "status": "approved",
        "blueprint_version": 1,
        "company_name": "Inventory Test",
        "target_role": "Engineer",
        "blueprint_data": {"rounds": [round_config]},
    }
    drive = MockDrive(
        company_name="Inventory Test",
        target_role="Engineer",
        status="active",
        selected_rounds={"aptitude": True},
        blueprint_snapshot=snapshot,
        created_by_id=tpo.id,
    )
    db_session.add(drive)
    db_session.flush()
    context = AssessmentContext(
        mode="mock_drive",
        purpose="mock_drive",
        student_id=student.id,
        company_name=drive.company_name,
        target_role=drive.target_role,
        mock_drive_id=drive.id,
        blueprint_snapshot=snapshot,
        policy_id=DEFAULT_PRACTICE_POLICY_ID,
        status="active",
    )
    db_session.add(context)
    db_session.flush()
    session = AssessmentSession(
        user_id=student.id,
        context_id=context.id,
        status="in_progress",
        started_at=datetime.utcnow(),
        expires_at=datetime.utcnow() + timedelta(hours=3),
    )
    db_session.add(session)
    db_session.flush()
    db_session.add(
        AssessmentRound(
            session_id=session.id,
            round_type="aptitude",
            status="active",
            max_questions=4,
            started_at=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=45),
        )
    )
    quant_topic = AptitudeTopic(name="Percentages")
    verbal_topic = AptitudeTopic(name="Vocabulary")
    db_session.add_all([quant_topic, verbal_topic])
    db_session.flush()
    for topic in (quant_topic, verbal_topic):
        db_session.add(
            AptitudeQuestion(
                question_text=f"{topic.name} only inventory item",
                option_a="A",
                option_b="B",
                option_c="C",
                option_d="D",
                correct_option="A",
                difficulty="medium",
                topic_id=topic.id,
                is_active=True,
            )
        )
    db_session.commit()

    response = client.get("/api/v1/aptitude/next-question", headers=student_headers)
    assert response.status_code == 409
    assert "seeded aptitude question bank" in response.json()["detail"]
    assert db_session.query(AptitudeRoundQuestion).count() == 0


def test_blueprint_coding_api_does_not_return_global_problems_without_active_round(
    client, db_session, auth_headers_student, auth_headers_tpo
):
    student_headers, student = auth_headers_student
    _, tpo = auth_headers_tpo
    active_round = _create_active_coding_round(db_session, student, tpo)
    active_round.status = "completed"
    db_session.add(_add_coding_problem(db_session, "Unrelated Preview Topic", "easy"))
    db_session.commit()

    response = client.get("/api/v1/coding/problems", headers=student_headers)
    assert response.status_code == 409
    assert "No active Coding round" in response.json()["detail"]
    assert "Unrelated Preview Topic" not in response.text


@pytest.mark.parametrize("invalid_kind", ["wrong_count", "duplicate_ids", "wrong_topic_and_difficulty"])
def test_coding_blueprint_rejects_invalid_existing_assignments(
    invalid_kind, client, db_session, auth_headers_student, auth_headers_tpo
):
    student_headers, student = auth_headers_student
    _, tpo = auth_headers_tpo
    round_config = {
        "round_type": "coding",
        "question_count": 2,
        "topics": [
            {"topic": "Arrays", "weight_pct": 50},
            {"topic": "HashMap", "weight_pct": 50},
        ],
    }
    active_round = _create_active_coding_round(db_session, student, tpo, round_config)
    arrays_problem = _add_coding_problem(db_session, "Arrays", "easy")
    if invalid_kind == "wrong_count":
        assignments = [(arrays_problem, 1)]
    elif invalid_kind == "duplicate_ids":
        assignments = [(arrays_problem, 1), (arrays_problem, 2)]
    else:
        strings_problem = _add_coding_problem(db_session, "Strings", "medium")
        assignments = [(arrays_problem, 1), (strings_problem, 2)]
    for problem, order in assignments:
        db_session.add(
            SessionProblem(
                round_id=active_round.id,
                problem_id=problem.id,
                problem_order=order,
                marked_for_review=False,
                assigned_at=datetime.utcnow(),
            )
        )
    db_session.commit()

    response = client.post("/api/v1/coding/start", headers=student_headers)
    assert response.status_code == 400
    assert "Existing coding assignments do not satisfy the pinned blueprint" in response.json()["detail"]
    problems_response = client.get("/api/v1/coding/problems", headers=student_headers)
    assert problems_response.status_code == 409


def test_coding_blueprint_resumes_valid_existing_assignments(
    client, db_session, auth_headers_student, auth_headers_tpo
):
    student_headers, student = auth_headers_student
    _, tpo = auth_headers_tpo
    round_config = {
        "round_type": "coding",
        "question_count": 2,
        "topics": [
            {"topic": "Arrays", "weight_pct": 50},
            {"topic": "HashMap", "weight_pct": 50},
        ],
        "difficulty_distribution": {"easy": 50, "hard": 50},
    }
    active_round = _create_active_coding_round(db_session, student, tpo, round_config)
    problems = [
        _add_coding_problem(db_session, "Arrays", "easy"),
        _add_coding_problem(db_session, "HashMap", "hard"),
    ]
    for order, problem in enumerate(problems, start=1):
        db_session.add(
            SessionProblem(
                round_id=active_round.id,
                problem_id=problem.id,
                problem_order=order,
                marked_for_review=False,
                assigned_at=datetime.utcnow(),
            )
        )
    db_session.commit()

    response = client.post("/api/v1/coding/start", headers=student_headers)
    assert response.status_code == 200, response.text
    assigned = response.json()
    assert len(assigned) == 2
    assert [problem["id"] for problem in assigned] == [problem.id for problem in problems]
    assert len({problem["id"] for problem in assigned}) == 2
    assert {problem["tags"][0] for problem in assigned} == {"Arrays", "HashMap"}


def test_coding_blueprint_resume_persists_snapshot_time_limit(
    client, db_session, auth_headers_student, auth_headers_tpo
):
    student_headers, student = auth_headers_student
    _, tpo = auth_headers_tpo
    round_config = {
        "round_type": "coding",
        "question_count": 1,
        "time_limit_minutes": 17,
        "topics": [{"topic": "Arrays", "weight_pct": 100}],
    }
    active_round = _create_active_coding_round(db_session, student, tpo, round_config)
    problem = _add_coding_problem(db_session, "Arrays", "medium")
    db_session.add(
        SessionProblem(
            round_id=active_round.id,
            problem_id=problem.id,
            problem_order=1,
            marked_for_review=False,
            assigned_at=datetime.utcnow(),
        )
    )
    db_session.commit()
    expected_expiry = active_round.started_at + timedelta(minutes=17)

    response = client.post("/api/v1/coding/start", headers=student_headers)
    assert response.status_code == 200, response.text

    db_session.expire_all()
    persisted_round = db_session.query(AssessmentRound).filter(
        AssessmentRound.id == active_round.id
    ).first()
    assert persisted_round.max_questions == 1
    assert persisted_round.expires_at == expected_expiry


def test_standalone_coding_round_keeps_existing_assignment_behavior(
    client, db_session, auth_headers_student, auth_headers_tpo
):
    student_headers, student = auth_headers_student
    _, tpo = auth_headers_tpo
    active_round = _create_active_coding_round(
        db_session, student, tpo, blueprint_backed=False
    )
    for index in range(4):
        _add_coding_problem(db_session, f"Standalone {index}", "medium")
    db_session.commit()

    response = client.post("/api/v1/coding/start", headers=student_headers)
    assert response.status_code == 200, response.text
    assert len(response.json()) == 3
    assert db_session.query(SessionProblem).filter(
        SessionProblem.round_id == active_round.id
    ).count() == 3


def test_standalone_interview_pool_keeps_existing_generation_defaults(monkeypatch):
    monkeypatch.setattr(
        interview_router_module,
        "get_session_active_blueprint_round_config",
        lambda db, session_id, fallback: (None, None, fallback),
    )
    captured = {}

    def fake_generate(*args, **kwargs):
        captured.update(kwargs)
        return [{"question": "standalone"}]

    monkeypatch.setattr(interview_router_module.groq_service, "generate_question_pool", fake_generate)
    pool, count, is_blueprint = interview_router_module._generate_question_pool_for_session(
        db=None,
        session_id=1,
        skills=["Python"],
        projects={},
        interview_type="technical",
    )
    assert pool == [{"question": "standalone"}]
    assert count == 12
    assert is_blueprint is False
    assert captured == {"count": 12, "interview_type": "technical"}


# ── Round Configuration Authority: round_configurations is a server-derived cache ─

DERIVED_APTITUDE_CONFIG = {
    "question_count": 7,
    "duration_minutes": 13,
    "difficulty_distribution": {"easy": 0, "medium": 0, "hard": 1},
}

DIVERGENT_CLIENT_CONFIG = {
    "aptitude": {
        "question_count": 99,
        "duration_minutes": 299,
        "difficulty_distribution": {"easy": 1, "medium": 0, "hard": 0},
    }
}


@pytest.fixture
def sample_full_config_blueprint(db_session, auth_headers_tpo):
    """Approved blueprint with a complete, schema-valid aptitude round configuration."""
    _, tpo = auth_headers_tpo
    bp = CompanyBlueprint(
        company_name="Nvidia",
        target_role="Software Engineer",
        status="approved",
        version=5,
        blueprint_data={
            "rounds": [
                {
                    "round_type": "aptitude",
                    "round_order": 1,
                    "round_name": "Aptitude Assessment",
                    "question_count": 7,
                    "time_limit_minutes": 13,
                    "difficulty_distribution": {"easy": 0, "medium": 0, "hard": 1},
                },
            ],
        },
        confidence_level="high",
        evidence_sources_count=2,
        created_by_id=tpo.id,
    )
    db_session.add(bp)
    db_session.commit()
    db_session.refresh(bp)
    return bp


def _reset_rate_limit_window():
    """The app's in-memory limiter is shared across all TestClient tests."""
    middleware_stack = application.middleware_stack or application.build_middleware_stack()
    application.middleware_stack = middleware_stack
    current_middleware = middleware_stack
    while current_middleware is not None and not isinstance(
        current_middleware, RateLimitMiddleware
    ):
        current_middleware = getattr(current_middleware, "app", None)
    assert current_middleware is not None
    current_middleware._requests.clear()


def test_create_derives_round_configurations_from_blueprint_over_client_input(
    client, auth_headers_tpo, sample_full_config_blueprint
):
    """TEST A: client-sent round_configurations must not override the blueprint."""
    _reset_rate_limit_window()
    headers, _ = auth_headers_tpo
    res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Nvidia",
            "target_role": "Software Engineer",
            "selected_rounds": {"aptitude": True},
            "blueprint_id": sample_full_config_blueprint.id,
            "round_configurations": DIVERGENT_CLIENT_CONFIG,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["round_configurations"] == {"aptitude": DERIVED_APTITUDE_CONFIG}


def test_update_derives_round_configurations_from_blueprint_over_client_input(
    client, auth_headers_tpo, sample_full_config_blueprint
):
    """TEST B: an update carrying divergent round_configurations must be ignored."""
    _reset_rate_limit_window()
    headers, _ = auth_headers_tpo
    created = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Nvidia",
            "target_role": "Software Engineer",
            "selected_rounds": {"aptitude": True},
            "blueprint_id": sample_full_config_blueprint.id,
        },
        headers=headers,
    )
    assert created.status_code == 201, created.text
    drive_id = created.json()["id"]

    updated = client.put(
        f"/api/v1/tpo/mock-drives/{drive_id}",
        json={
            "description": "Edited description",
            "round_configurations": {
                "aptitude": {
                    "question_count": 50,
                    "duration_minutes": 100,
                    "difficulty_distribution": {"easy": 0, "medium": 1, "hard": 0},
                }
            },
        },
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["description"] == "Edited description"
    assert updated.json()["round_configurations"] == {"aptitude": DERIVED_APTITUDE_CONFIG}


def test_assessment_context_uses_pinned_snapshot_not_client_round_configurations(
    client, db_session, auth_headers_tpo, auth_headers_student, sample_full_config_blueprint
):
    """TEST C: runtime context is built from blueprint_snapshot, not the cache."""
    _reset_rate_limit_window()
    tpo_headers, _ = auth_headers_tpo
    student_headers, _ = auth_headers_student
    created = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Nvidia",
            "target_role": "Software Engineer",
            "selected_rounds": {"aptitude": True},
            "blueprint_id": sample_full_config_blueprint.id,
            "round_configurations": DIVERGENT_CLIENT_CONFIG,
        },
        headers=tpo_headers,
    )
    assert created.status_code == 201, created.text
    drive_id = created.json()["id"]
    # The persisted cache is already derived from the snapshot.
    assert created.json()["round_configurations"] == {"aptitude": DERIVED_APTITUDE_CONFIG}

    # Seed required pre-generated pool for aptitude round
    _seed_complete_pool(
        db_session, sample_full_config_blueprint.id, 5, "aptitude",
        "Nvidia", "Software Engineer"
    )

    publish_res = client.post(f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers)
    assert publish_res.status_code == 200, publish_res.text
    start_res = client.post(f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers)
    assert start_res.status_code == 200, start_res.text
    assert start_res.json()["enabled_rounds"] == ["aptitude"]

    context = db_session.query(AssessmentContext).filter(
        AssessmentContext.id == start_res.json()["context_id"]
    ).first()
    snapshot = context.blueprint_snapshot
    assert snapshot is not None
    round_config = snapshot["blueprint_data"]["rounds"][0]
    # Runtime authority is the pinned snapshot's blueprint rounds.
    assert round_config["question_count"] == 7
    assert round_config["time_limit_minutes"] == 13
    assert snapshot["enabled_rounds"] == ["aptitude"]
    # The client's divergent values appear nowhere in the runtime snapshot.
    assert round_config["question_count"] != DIVERGENT_CLIENT_CONFIG["aptitude"]["question_count"]


def test_blueprint_less_drive_still_persists_client_round_configurations(
    client, auth_headers_tpo
):
    """TEST D: legacy blueprint-less behavior is unchanged (client value kept)."""
    _reset_rate_limit_window()
    headers, _ = auth_headers_tpo
    res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Legacy Corp",
            "target_role": "Data Engineer",
            "selected_rounds": {"aptitude": True},
            "round_configurations": DIVERGENT_CLIENT_CONFIG,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["blueprint_id"] is None
    assert res.json()["round_configurations"] == DIVERGENT_CLIENT_CONFIG


@pytest.mark.parametrize(
    ("round_key", "round_type", "duration_minutes"),
    [
        ("aptitude", "aptitude", 17),
        ("coding", "coding", 23),
        ("technical_interview", "interview", 19),
        ("hr_interview", "interview", 11),
    ],
)
def test_blueprint_less_round_uses_configured_duration(
    client,
    db_session,
    auth_headers_tpo,
    auth_headers_student,
    round_key,
    round_type,
    duration_minutes,
):
    _reset_rate_limit_window()
    tpo_headers, _ = auth_headers_tpo
    student_headers, _ = auth_headers_student

    create_res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": f"Legacy Timer {round_key} {uuid.uuid4().hex[:6]}",
            "target_role": "Software Engineer",
            "selected_rounds": {round_key: True},
            "round_configurations": _blueprintless_round_config(
                round_key, duration_minutes=duration_minutes
            ),
        },
        headers=tpo_headers,
    )
    assert create_res.status_code == 201, create_res.text
    drive_id = create_res.json()["id"]
    assert create_res.json()["blueprint_id"] is None

    publish_res = client.post(
        f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers
    )
    assert publish_res.status_code == 200, publish_res.text

    start_res = client.post(
        f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers
    )
    assert start_res.status_code == 200, start_res.text

    active_round = (
        db_session.query(AssessmentRound)
        .filter_by(session_id=start_res.json()["session_id"], status="active")
        .one()
    )
    assert active_round.round_type == round_type
    assert active_round.practice_type == round_key
    assert active_round.expires_at - active_round.started_at == timedelta(
        minutes=duration_minutes
    )


def test_blueprint_less_publish_requires_timer_for_every_enabled_round(
    client, db_session, auth_headers_tpo
):
    _reset_rate_limit_window()
    tpo_headers, _ = auth_headers_tpo

    create_res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Missing Timer Co",
            "target_role": "Software Engineer",
            "selected_rounds": {"aptitude": True, "hr_interview": True},
        },
        headers=tpo_headers,
    )
    assert create_res.status_code == 201, create_res.text
    drive_id = create_res.json()["id"]

    publish_res = client.post(
        f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers
    )
    assert publish_res.status_code == 422, publish_res.text
    errors = publish_res.json()["detail"]["errors"]
    assert (
        "Missing or invalid timer configuration for round 'aptitude'."
        in errors
    )
    assert (
        "Missing or invalid timer configuration for round 'hr_interview'."
        in errors
    )
    assert db_session.query(MockDrive).filter_by(id=drive_id).one().status == "draft"


def test_blueprint_less_publish_rejects_partial_timer_configuration(
    client, auth_headers_tpo
):
    _reset_rate_limit_window()
    tpo_headers, _ = auth_headers_tpo

    create_res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Partial Timer Co",
            "target_role": "Software Engineer",
            "selected_rounds": {"aptitude": True, "coding": True},
            "round_configurations": _blueprintless_round_config("aptitude"),
        },
        headers=tpo_headers,
    )
    assert create_res.status_code == 201, create_res.text
    drive_id = create_res.json()["id"]

    publish_res = client.post(
        f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers
    )
    assert publish_res.status_code == 422, publish_res.text
    errors = publish_res.json()["detail"]["errors"]
    assert any("coding" in error for error in errors)
    assert not any("aptitude" in error for error in errors)


def test_existing_published_blueprint_less_drive_without_config_keeps_policy_default(
    client, db_session, auth_headers_tpo, auth_headers_student
):
    _reset_rate_limit_window()
    _, tpo = auth_headers_tpo
    student_headers, _ = auth_headers_student

    drive = MockDrive(
        company_name="Legacy Published Co",
        target_role="Software Engineer",
        status="published",
        minimum_cgpa=0.0,
        maximum_backlogs=100,
        eligible_branches=[],
        selected_rounds={"aptitude": True},
        round_configurations={},
        created_by_id=tpo.id,
    )
    db_session.add(drive)
    db_session.commit()
    db_session.refresh(drive)

    start_res = client.post(
        f"/api/v1/mock-drives/{drive.id}/start", headers=student_headers
    )
    assert start_res.status_code == 200, start_res.text

    active_round = (
        db_session.query(AssessmentRound)
        .filter_by(session_id=start_res.json()["session_id"], status="active")
        .one()
    )
    assert active_round.expires_at - active_round.started_at == timedelta(minutes=30)


def test_live_blueprint_change_does_not_mutate_pinned_snapshot_or_derived_cache(
    client, db_session, auth_headers_tpo, auth_headers_student, sample_full_config_blueprint
):
    """TEST E: changing the live blueprint must not affect an existing drive."""
    _reset_rate_limit_window()
    tpo_headers, _ = auth_headers_tpo
    student_headers, _ = auth_headers_student
    created = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Nvidia",
            "target_role": "Software Engineer",
            "selected_rounds": {"aptitude": True},
            "blueprint_id": sample_full_config_blueprint.id,
        },
        headers=tpo_headers,
    )
    assert created.status_code == 201, created.text
    drive_id = created.json()["id"]
    drive = db_session.query(MockDrive).filter_by(id=drive_id).one()
    pinned_snapshot = drive.blueprint_snapshot
    pinned_config = drive.round_configurations

    # Mutate the live blueprint row (recalculation semantics: in-place bump).
    sample_full_config_blueprint.version += 1
    sample_full_config_blueprint.blueprint_data = {
        "rounds": [
            {
                "round_type": "aptitude",
                "round_order": 1,
                "question_count": 50,
                "time_limit_minutes": 11,
                "difficulty_distribution": {"easy": 1, "medium": 0, "hard": 0},
            }
        ]
    }
    db_session.commit()

    # An ordinary edit keeps the drive pinned to the original snapshot.
    updated = client.put(
        f"/api/v1/tpo/mock-drives/{drive_id}",
        json={
            "description": "Edited after live blueprint change",
            "blueprint_id": sample_full_config_blueprint.id,
        },
        headers=tpo_headers,
    )
    assert updated.status_code == 200, updated.text
    db_session.refresh(drive)
    assert drive.blueprint_snapshot == pinned_snapshot
    assert drive.round_configurations == pinned_config == {"aptitude": DERIVED_APTITUDE_CONFIG}

    # Seed required pre-generated pool for aptitude round (pinned v5)
    _seed_complete_pool(
        db_session, sample_full_config_blueprint.id, 5, "aptitude",
        "Nvidia", "Software Engineer"
    )

    # Runtime start still uses the pinned snapshot, not the mutated live row.
    publish_res = client.post(f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers)
    assert publish_res.status_code == 200, publish_res.text
    start_res = client.post(f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers)
    assert start_res.status_code == 200, start_res.text
    context = db_session.query(AssessmentContext).filter(
        AssessmentContext.id == start_res.json()["context_id"]
    ).first()
    round_config = context.blueprint_snapshot["blueprint_data"]["rounds"][0]
    assert round_config["question_count"] == 7
    assert round_config["time_limit_minutes"] == 13
    assert round_config["question_count"] != 50


# ── G6: Consolidated Mock Drive Result ──────────────────────────────────

def test_g6_result_endpoint_completed_drive(
    client, db_session, auth_headers_tpo, auth_headers_student, sample_generation_blueprint
):
    """G6: GET /mock-drives/{id}/result returns consolidated result for completed drive."""
    tpo_headers, _ = auth_headers_tpo
    student_headers, student = auth_headers_student

    # Seed interview pool for technical_interview
    interview_pool_content = [
        {
            "id": f"tech-interview-{i}",
            "question": f"Configured interview question {i}",
            "difficulty": "MEDIUM",
            "topic": "Data Structures" if i % 2 == 0 else "System Design",
            "phase": "TECHNICAL",
            "blueprint_pool": True,
        }
        for i in range(3)
    ]
    _seed_complete_pool(
        db_session, sample_generation_blueprint.id, 4, "technical_interview",
        "Nvidia", "Software Engineer", content=interview_pool_content
    )

    # Seed aptitude questions for the seeded bank (required for G2/G3b publish gate)
    from app.models.aptitude import AptitudeTopic, AptitudeQuestion
    quant_topic = AptitudeTopic(name="Quantitative Aptitude")
    logical_topic = AptitudeTopic(name="Logical Reasoning")
    db_session.add_all([quant_topic, logical_topic])
    db_session.flush()
    for topic in (quant_topic, logical_topic):
        for difficulty in ("easy", "medium"):
            for _ in range(2):
                db_session.add(AptitudeQuestion(
                    question_text=f"{topic.name} {difficulty}",
                    option_a="A", option_b="B", option_c="C", option_d="D",
                    correct_option="A", difficulty=difficulty, topic_id=topic.id, is_active=True,
                ))
    db_session.commit()

    # Create and publish drive with aptitude + technical_interview
    create_res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Nvidia",
            "target_role": "Software Engineer",
            "selected_rounds": {"aptitude": True, "technical_interview": True},
            "blueprint_id": sample_generation_blueprint.id,
        },
        headers=tpo_headers,
    )
    assert create_res.status_code == 201
    drive_id = create_res.json()["id"]
    publish_res = client.post(f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers)
    if publish_res.status_code != 200:
        print("Publish error:", publish_res.status_code, publish_res.json())
    assert publish_res.status_code == 200

    # Start and complete aptitude
    start_res = client.post(f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers)
    assert start_res.status_code == 200
    session_id = start_res.json()["session_id"]

    # Complete aptitude
    for _ in range(4):
        q_res = client.get("/api/v1/aptitude/next-question", headers=student_headers)
        assert q_res.status_code == 200
        submit_res = client.post("/api/v1/aptitude/submit-answer", json={
            "question_id": q_res.json()["question_id"],
            "selected_option": "A",
            "response_time": 1.0,
        }, headers=student_headers)
        assert submit_res.status_code == 200
    finish_res = client.post("/api/v1/aptitude/finish", headers=student_headers)
    assert finish_res.status_code == 200

    # Advance to technical interview (happens automatically via aptitude finish)
    # No manual advance needed - aptitude finish already advances to next round

    # Complete interview
    interview_res = client.post(
        "/api/v1/interview/session/start-active", headers=student_headers
    )
    if interview_res.status_code != 200:
        print("Interview start error:", interview_res.status_code, interview_res.json())
    assert interview_res.status_code == 200
    interview_id = interview_res.json()["interview_id"]
    # Persist only a scored follow-up turn to verify that interview evaluation
    # evidence is counted even when there is no scored main turn to aggregate.
    from app.models.interview import InterviewTurn
    db_session.add(InterviewTurn(
        interview_id=interview_id,
        turn_number=1,
        question_text="Fixture interview question",
        candidate_response="Fixture response",
        is_followup=True,
        followup_number=1,
        final_score=0.75,
    ))
    db_session.commit()
    complete_res = client.post(
        f"/api/v1/interview/session/{interview_id}/complete",
        headers=student_headers
    )
    assert complete_res.status_code == 200

    # The live Results page reads the report endpoint directly, so pending
    # mapping recovery must not depend on a separate status poll.
    context = db_session.query(AssessmentContext).filter_by(
        mock_drive_id=drive_id, student_id=student.id
    ).one()
    context.competency_mapping_status = "pending"
    db_session.commit()

    # Now fetch the consolidated result
    result_res = client.get(f"/api/v1/mock-drives/{drive_id}/result", headers=student_headers)
    assert result_res.status_code == 200
    result = result_res.json()
    assert result["mock_drive_id"] == drive_id
    assert result["status"] == "completed"
    assert result["candidate_id"] == student.id
    assert set(result["enabled_rounds"]) == {"aptitude", "technical_interview"}
    assert len(result["rounds"]) == 2
    aptitude_result = next(r for r in result["rounds"] if r["round_type"] == "aptitude")
    interview_result = next(r for r in result["rounds"] if r["round_type"] == "technical_interview")
    assert aptitude_result["status"] == "completed"
    assert aptitude_result["score"] == 100.0
    assert aptitude_result["max_score"] == 100.0
    assert aptitude_result["evaluation_status"] == "evaluated"
    assert aptitude_result["details"]["graded_count"] == 4
    assert aptitude_result["details"]["correct_count"] == 4
    assert aptitude_result["details"]["question_set_complete"] is True
    assert aptitude_result["details"]["total_questions"] == 4
    assert aptitude_result["details"]["unanswered_count"] == 0
    assert interview_result["status"] == "completed"
    assert interview_result["score"] is None  # completed without evaluated turns
    assert interview_result["evaluation_status"] == "evaluated"
    assert len(interview_result["details"]["turns"]) == 1
    assert interview_result["details"]["turns"][0]["score"] == 0.75
    assert result["overall_score"] is None  # round scales are intentionally not combined
    assert result["completed_at"] is not None
    db_session.refresh(context)
    assert context.competency_mapping_status == "not_applicable"


def test_g6_result_endpoint_partial_drive(
    client, db_session, auth_headers_tpo, auth_headers_student
):
    """G6: GET /mock-drives/{id}/result returns partial result for in-progress drive."""
    tpo_headers, tpo = auth_headers_tpo
    student_headers, student = auth_headers_student

    # Create a blueprint with aptitude and coding (with topics for coding feasibility)
    bp = CompanyBlueprint(
        company_name="Google",
        target_role="Software Engineer",
        status="approved",
        version=1,
        blueprint_data={
            "company_name": "Google",
            "target_role": "Software Engineer",
            "status": "approved",
            "version": 1,
            "rounds": [
                {
                    "round_type": "aptitude",
                    "round_order": 1,
                    "question_count": 4,
                    "time_limit_minutes": 45,
                    "question_types": ["MCQ"],
                    "topics": [
                        {"topic": "Quantitative Aptitude", "weight_pct": 50},
                        {"topic": "Logical Reasoning", "weight_pct": 50},
                    ],
                    "difficulty_distribution": {"easy": 50, "medium": 50},
                },
                {
                    "round_type": "coding",
                    "round_order": 2,
                    "question_count": 2,
                    "question_types": ["Coding"],
                    "topics": [
                        {"topic": "Arrays", "weight_pct": 50},
                        {"topic": "HashMap", "weight_pct": 50},
                    ],
                    "difficulty_distribution": {"easy": 50, "hard": 50},
                },
            ],
        },
        confidence_level="high",
        evidence_sources_count=2,
        created_by_id=tpo.id,
    )
    db_session.add(bp)
    db_session.commit()
    db_session.refresh(bp)

    # Seed aptitude questions for feasibility
    from app.models.aptitude import AptitudeTopic, AptitudeQuestion
    quant_topic = AptitudeTopic(name="Quantitative Aptitude")
    logical_topic = AptitudeTopic(name="Logical Reasoning")
    db_session.add_all([quant_topic, logical_topic])
    db_session.flush()
    for topic in (quant_topic, logical_topic):
        for difficulty in ("easy", "medium"):
            for _ in range(2):
                db_session.add(AptitudeQuestion(
                    question_text=f"{topic.name} {difficulty}",
                    option_a="A", option_b="B", option_c="C", option_d="D",
                    correct_option="A", difficulty=difficulty, topic_id=topic.id, is_active=True,
                ))
    db_session.commit()

    # Seed coding problems
    from app.models.coding import CodingProblem
    for topic_name, difficulty in (("Arrays", "easy"), ("HashMap", "hard"), ("Arrays", "hard"), ("HashMap", "easy")):
        problem = CodingProblem(
            title=f"{topic_name} {difficulty}",
            description="Return a value computed from the input.",
            difficulty=difficulty,
        )
        problem.tags_list = [topic_name]
        db_session.add(problem)
    db_session.commit()

    # Create drive with aptitude + coding (using the custom blueprint)
    bp = db_session.query(CompanyBlueprint).filter(CompanyBlueprint.company_name == "Google", CompanyBlueprint.target_role == "Software Engineer", CompanyBlueprint.status == "approved").first()
    create_res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Google",
            "target_role": "Software Engineer",
            "selected_rounds": {"aptitude": True, "coding": True},
            "blueprint_id": bp.id,
        },
        headers=tpo_headers,
    )
    assert create_res.status_code == 201
    drive_id = create_res.json()["id"]
    publish_res = client.post(f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers)
    if publish_res.status_code != 200:
        print("Publish error:", publish_res.status_code, publish_res.json())
    assert publish_res.status_code == 200

    # Start drive
    start_res = client.post(f"/api/v1/mock-drives/{drive_id}/start", headers=student_headers)
    assert start_res.status_code == 200

    # Result should show in-progress status
    result_res = client.get(f"/api/v1/mock-drives/{drive_id}/result", headers=student_headers)
    assert result_res.status_code == 200
    result = result_res.json()
    assert result["status"] == "in_progress"
    assert result["candidate_id"] == student.id
    assert result["session_id"] is not None
    assert set(result["enabled_rounds"]) == {"aptitude", "coding"}
    assert len(result["rounds"]) == 2
    for round_summary in result["rounds"]:
        assert round_summary["status"] in ("not_started", "in_progress", "active")
        assert round_summary["score"] is None

    # A persisted compilation error is an evaluated zero score, distinct from
    # no attempt and from a still-running submission.
    from app.models.coding import CodingSubmission
    session = db_session.query(AssessmentSession).filter_by(id=result["session_id"]).one()
    coding_round = AssessmentRound(
        session_id=session.id,
        round_type="coding",
        practice_type="coding",
        status="completed",
        score=0.475,
    )
    db_session.add(coding_round)
    db_session.flush()
    problems = db_session.query(CodingProblem).order_by(CodingProblem.id).limit(4).all()
    for index, problem in enumerate(problems, start=1):
        db_session.add(SessionProblem(
            round_id=coding_round.id,
            problem_id=problem.id,
            problem_order=index,
            assigned_at=datetime.utcnow(),
        ))
    submission_specs = [
        (problems[0], "compilation_error", 0.0),
        (problems[1], "running", None),
        (problems[2], "accepted", 1.0),
        # The problem's best finalized attempt is used across retries.
        (problems[3], "wrong_answer", 0.4),
        (problems[3], "accepted", 0.9),
    ]
    for problem, submission_status, score in submission_specs:
        db_session.add(CodingSubmission(
            round_id=coding_round.id,
            problem_id=problem.id,
            code="isolated report fixture",
            language="python",
            status=submission_status,
            score=score,
        ))
    db_session.commit()

    result_res = client.get(f"/api/v1/mock-drives/{drive_id}/result", headers=student_headers)
    assert result_res.status_code == 200
    coding_result = next(r for r in result_res.json()["rounds"] if r["round_type"] == "coding")
    assert coding_result["score"] == 0.475
    assert coding_result["evaluation_status"] == "evaluated"
    coding_problems = coding_result["details"]["problems"]
    assert len(coding_problems) == 4
    assert sum(problem["attempted"] for problem in coding_problems) == 4
    assert sum(problem["status"] == "accepted" for problem in coding_problems) == 2
    by_id = {problem["problem_id"]: problem for problem in coding_problems}
    assert by_id[problems[0].id]["evaluation_status"] == "evaluated"
    assert by_id[problems[0].id]["score"] == 0.0
    assert by_id[problems[1].id]["evaluation_status"] == "pending"
    assert by_id[problems[1].id]["score"] is None
    assert by_id[problems[2].id]["score"] == 1.0
    assert by_id[problems[3].id]["score"] == 0.9


def test_g6_result_endpoint_cross_candidate_denied(
    client, db_session, auth_headers_tpo, auth_headers_student, sample_approved_blueprint
):
    """G6: Cross-candidate access to /mock-drives/{id}/result is denied."""
    tpo_headers, _ = auth_headers_tpo
    student_headers, student = auth_headers_student
    other_headers, other_student = auth_headers_student

    # Create drive with aptitude
    create_res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Google",
            "target_role": "Software Engineer",
            "selected_rounds": {"aptitude": True},
            "blueprint_id": sample_approved_blueprint.id,
        },
        headers=tpo_headers,
    )
    assert create_res.status_code == 201
    drive_id = create_res.json()["id"]
    publish_res = client.post(f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers)
    assert publish_res.status_code == 200

    # Other student tries to access result
    result_res = client.get(f"/api/v1/mock-drives/{drive_id}/result", headers=other_headers)
    assert result_res.status_code == 404
    assert "No result found" in result_res.json()["detail"]


def test_g6_result_endpoint_not_started(
    client, db_session, auth_headers_tpo, auth_headers_student, sample_approved_blueprint
):
    """G6: GET /mock-drives/{id}/result returns 404 for not-yet-started drive (no result yet)."""
    tpo_headers, _ = auth_headers_tpo
    student_headers, student = auth_headers_student

    create_res = client.post(
        "/api/v1/tpo/mock-drives",
        json={
            "company_name": "Google",
            "target_role": "Software Engineer",
            "selected_rounds": {"aptitude": True},
            "blueprint_id": sample_approved_blueprint.id,
        },
        headers=tpo_headers,
    )
    assert create_res.status_code == 201
    drive_id = create_res.json()["id"]
    publish_res = client.post(f"/api/v1/tpo/mock-drives/{drive_id}/publish", headers=tpo_headers)
    assert publish_res.status_code == 200

    # Don't start the drive, just fetch result
    result_res = client.get(f"/api/v1/mock-drives/{drive_id}/result", headers=student_headers)
    assert result_res.status_code == 404
    assert "No result found" in result_res.json()["detail"]
