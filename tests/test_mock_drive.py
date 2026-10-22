"""
Tests for Phase 2: TPO Mock Drive Management.

Covers all 14 acceptance criteria from the spec:
 1.  TPO can create a Mock Drive
 2.  Admin can create a Mock Drive
 3.  Student cannot create a Mock Drive (403)
 4.  Faculty cannot create a Mock Drive (403)
 5.  Newly created drive has status=draft
 6.  TPO can list drives
 7.  TPO can retrieve a drive by id
 8.  TPO can update a draft drive
 9.  TPO can delete a draft drive
10.  Invalid round names are rejected (422)
11.  Empty company name is rejected (422)
12.  Empty target role is rejected (422)
13.  At least one round is required (422)
14.  Non-draft drives cannot be edited or deleted (422)
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles

from app.database.db import get_db
from app.database.base import Base
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

# Enable FK enforcement in SQLite so cascade deletes work
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

# Force-import all models so Base.metadata is complete
import app.models.user               # noqa: F401, E402
import app.models.assessment         # noqa: F401, E402
import app.models.profile            # noqa: F401, E402
import app.models.assessment_context # noqa: F401, E402
import app.models.mock_drive         # noqa: F401, E402

Base.metadata.create_all(bind=engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="module", autouse=True)
def setup_mock_drive_db():
    application.dependency_overrides[get_db] = override_get_db
    yield
    application.dependency_overrides.pop(get_db, None)


client = TestClient(application)

# ── Fixtures ──────────────────────────────────────────────────────────

def _register_and_login(role: str) -> dict:
    """Register a user with the given role and return auth headers."""
    uid = uuid.uuid4().hex[:8]
    email = f"mock_drive_{role}_{uid}@test.com"
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


VALID_PAYLOAD = {
    "company_name": "Citi",
    "target_role": "Data Engineer",
    "description": "A Citi mock drive for Phase 2 testing.",
    "minimum_cgpa": 6.5,
    "maximum_backlogs": 1,
    "eligible_branches": ["Computer Science", "Information Technology"],
    "selected_rounds": {
        "aptitude": True,
        "coding": True,
        "technical_interview": False,
        "hr_interview": False,
    },
}

BASE_URL = "/api/v1/tpo/mock-drives"

# ── Tests ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def tpo_headers():
    return _register_and_login("tpo")


@pytest.fixture(scope="module")
def admin_headers():
    return _register_and_login("admin")


@pytest.fixture(scope="module")
def student_headers():
    return _register_and_login("student")


@pytest.fixture(scope="module")
def faculty_headers():
    return _register_and_login("faculty")


# 1. TPO can create a Mock Drive
def test_tpo_can_create(tpo_headers):
    res = client.post(BASE_URL, json=VALID_PAYLOAD, headers=tpo_headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["company_name"] == "Citi"
    assert data["target_role"] == "Data Engineer"


# 2. Admin can create a Mock Drive
def test_admin_can_create(admin_headers):
    payload = {**VALID_PAYLOAD, "company_name": "Admin Corp", "target_role": "SRE"}
    res = client.post(BASE_URL, json=payload, headers=admin_headers)
    assert res.status_code == 201, res.text


# 3. Student cannot create (403)
def test_student_cannot_create(student_headers):
    res = client.post(BASE_URL, json=VALID_PAYLOAD, headers=student_headers)
    assert res.status_code == 403, res.text


# 4. Faculty cannot create (403)
def test_faculty_cannot_create(faculty_headers):
    res = client.post(BASE_URL, json=VALID_PAYLOAD, headers=faculty_headers)
    assert res.status_code == 403, res.text


# 5. Newly created drive has status=draft
def test_new_drive_is_draft(tpo_headers):
    res = client.post(BASE_URL, json=VALID_PAYLOAD, headers=tpo_headers)
    assert res.status_code == 201
    assert res.json()["status"] == "draft"


# 6. TPO can list drives
def test_tpo_can_list(tpo_headers):
    res = client.get(BASE_URL, headers=tpo_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)


# 7. TPO can retrieve a drive by id
def test_tpo_can_get_single(tpo_headers):
    create_res = client.post(BASE_URL, json=VALID_PAYLOAD, headers=tpo_headers)
    assert create_res.status_code == 201
    drive_id = create_res.json()["id"]

    get_res = client.get(f"{BASE_URL}/{drive_id}", headers=tpo_headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == drive_id


# 8. TPO can update a draft drive
def test_tpo_can_update_draft(tpo_headers):
    create_res = client.post(BASE_URL, json=VALID_PAYLOAD, headers=tpo_headers)
    drive_id = create_res.json()["id"]

    update_res = client.put(
        f"{BASE_URL}/{drive_id}",
        json={"company_name": "Updated Corp", "target_role": "Backend Engineer"},
        headers=tpo_headers,
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["company_name"] == "Updated Corp"
    assert updated["target_role"] == "Backend Engineer"


# 9. TPO can delete a draft drive
def test_tpo_can_delete_draft(tpo_headers):
    create_res = client.post(BASE_URL, json=VALID_PAYLOAD, headers=tpo_headers)
    drive_id = create_res.json()["id"]

    del_res = client.delete(f"{BASE_URL}/{drive_id}", headers=tpo_headers)
    assert del_res.status_code == 204

    # Confirm 404 after deletion
    get_res = client.get(f"{BASE_URL}/{drive_id}", headers=tpo_headers)
    assert get_res.status_code == 404


# 10. Invalid round names are rejected
def test_invalid_rounds_rejected(tpo_headers):
    bad_payload = {**VALID_PAYLOAD, "selected_rounds": {"unknown_round": True}}
    res = client.post(BASE_URL, json=bad_payload, headers=tpo_headers)
    assert res.status_code == 422, res.text


# 11. Empty company name is rejected
def test_empty_company_name_rejected(tpo_headers):
    bad_payload = {**VALID_PAYLOAD, "company_name": ""}
    res = client.post(BASE_URL, json=bad_payload, headers=tpo_headers)
    assert res.status_code == 422, res.text


# 12. Empty target role is rejected
def test_empty_target_role_rejected(tpo_headers):
    bad_payload = {**VALID_PAYLOAD, "target_role": ""}
    res = client.post(BASE_URL, json=bad_payload, headers=tpo_headers)
    assert res.status_code == 422, res.text


# 13. At least one round is required
def test_no_rounds_rejected(tpo_headers):
    bad_payload = {
        **VALID_PAYLOAD,
        "selected_rounds": {
            "aptitude": False,
            "coding": False,
            "technical_interview": False,
            "hr_interview": False,
        },
    }
    res = client.post(BASE_URL, json=bad_payload, headers=tpo_headers)
    assert res.status_code == 422, res.text


# 14. Non-draft drives cannot be edited or deleted
def test_non_draft_cannot_be_modified(tpo_headers):
    """Manually force status to 'published' at the DB level and verify 422."""
    # Create a drive first
    create_res = client.post(BASE_URL, json=VALID_PAYLOAD, headers=tpo_headers)
    drive_id = create_res.json()["id"]

    # Directly flip status to 'published' in the test DB
    db = TestingSessionLocal()
    try:
        db.execute(
            text("UPDATE mock_drives SET status = 'published' WHERE id = :id"),
            {"id": drive_id},
        )
        db.commit()
    finally:
        db.close()

    # Edit should now return 422
    edit_res = client.put(
        f"{BASE_URL}/{drive_id}",
        json={"company_name": "Should Fail"},
        headers=tpo_headers,
    )
    assert edit_res.status_code == 422, edit_res.text

    # Delete should also return 422
    del_res = client.delete(f"{BASE_URL}/{drive_id}", headers=tpo_headers)
    assert del_res.status_code == 422, del_res.text


# 15. Creation with unset optional eligibility fields falls back to schema defaults
def test_create_omitting_cgpa_and_backlogs_uses_defaults(tpo_headers):
    payload = {
        k: v for k, v in VALID_PAYLOAD.items()
        if k not in ("minimum_cgpa", "maximum_backlogs")
    }
    res = client.post(BASE_URL, json=payload, headers=tpo_headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["minimum_cgpa"] == 6.0
    assert data["maximum_backlogs"] == 0


# 16. Explicitly provided eligibility values are persisted unchanged
def test_create_with_explicit_cgpa_and_backlogs_preserves_values(tpo_headers):
    res = client.post(BASE_URL, json=VALID_PAYLOAD, headers=tpo_headers)
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["minimum_cgpa"] == 6.5
    assert data["maximum_backlogs"] == 1


# 17. Backend validation is not weakened: null eligibility values still 422
def test_null_cgpa_and_backlogs_still_rejected(tpo_headers):
    payload = {**VALID_PAYLOAD, "minimum_cgpa": None, "maximum_backlogs": None}
    res = client.post(BASE_URL, json=payload, headers=tpo_headers)
    assert res.status_code == 422, res.text


# Cleanup
def teardown_module(module):
    application.dependency_overrides.clear()
