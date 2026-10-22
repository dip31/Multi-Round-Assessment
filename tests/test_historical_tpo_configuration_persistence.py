"""Durable historical TPO configuration persistence.

Verifies the reported defects in the historical assessment configuration flow:

  * A TPO-added round survives recalculation (previously it vanished because it
    only existed in the request that added it).
  * TPO-edited round values (question count / duration / difficulty / topics)
    survive recalculation (previously "Recalculate Pattern" wiped them).
  * Explicit deselection is durable and is distinguishable from an unspecified
    round; source-level historical evidence is never erased.
  * Legacy patterns without a ``tpo_configuration`` block load compatibly.

These drive the real HTTP chain and assert the persisted values returned by the
API, so they fail if the fix is only applied in the UI layer.
"""

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
def setup_db_override():
    application.dependency_overrides[get_db] = override_get_db
    yield
    application.dependency_overrides.pop(get_db, None)


client = TestClient(application)

HISTORICAL_URL = "/api/v1/tpo/company-data/historical"
PATTERN_URL = "/api/v1/tpo/company-data/pattern"


@pytest.fixture(scope="module")
def tpo_headers():
    uid = uuid.uuid4().hex[:8]
    email = f"tpoconfig_{uid}@test.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"name": "Test TPO", "email": email, "password": "Password@123", "role": "tpo"},
    )
    assert reg.status_code in (200, 201), reg.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "Password@123"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _add_complete_source(headers, company, role):
    res = client.post(
        HISTORICAL_URL,
        json={
            "company_name": company,
            "target_role": role,
            "label": "Evidence",
            "raw_data": {
                "rounds": ["aptitude", "coding"],
                "topics": ["Quantitative Aptitude", "Arrays", "Dynamic Programming"],
                "difficulty": "medium",
                "round_patterns": {
                    "aptitude": {
                        "duration_minutes": 30,
                        "question_count": 20,
                        "focus_areas": ["Quantitative Aptitude"],
                    },
                    "coding": {
                        "duration_minutes": 60,
                        "question_count": 5,
                        "focus_areas": ["Arrays", "Dynamic Programming"],
                    },
                },
            },
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text


def _generate(headers, company, role, body=None):
    res = client.post(
        f"{PATTERN_URL}/generate",
        json={"company_name": company, "target_role": role, **(body or {})},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    return res.json()["pattern_data"]


def _get_pattern(headers, company, role):
    res = client.get(f"{PATTERN_URL}/{company}/{role}", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()["pattern_data"]


def _historical_count(headers):
    res = client.get(HISTORICAL_URL, headers=headers)
    assert res.status_code == 200, res.text
    return len(res.json())


def test_tpo_added_round_survives_recalculation(tpo_headers):
    company, role = "PersistAddedCo", "SDE"
    _add_complete_source(tpo_headers, company, role)

    first = _generate(tpo_headers, company, role, {"added_rounds": ["hr_interview"]})
    assert "hr_interview" in first["assessment_rounds"]

    # Recalculate with no configuration at all: the TPO-added round must persist.
    second = _generate(tpo_headers, company, role)
    assert "hr_interview" in second["assessment_rounds"]
    assert any(
        entry["round_type"] == "hr_interview"
        and entry["enabled"] is True
        and entry["round_origin"] == "tpo_added"
        for entry in second["tpo_configuration"]["rounds"]
    )

    # ... and it stays persisted in the stored pattern read back over HTTP.
    stored = _get_pattern(tpo_headers, company, role)
    assert "hr_interview" in stored["assessment_rounds"]


def test_tpo_edited_round_values_survive_recalculation(tpo_headers):
    company, role = "PersistEditedCo", "SDE"
    _add_complete_source(tpo_headers, company, role)

    _generate(
        tpo_headers,
        company,
        role,
        {
            "round_configuration": [
                {
                    "round_type": "coding",
                    "question_count": 40,
                    "duration_minutes": 90,
                    "difficulty_distribution": {"easy": 0.0, "medium": 1.0, "hard": 0.0},
                }
            ]
        },
    )

    # Recalculate with no configuration: the TPO-edited values must persist.
    recalc = _generate(tpo_headers, company, role)
    coding = recalc["round_patterns"]["coding"]
    assert coding["question_count"] == 40
    assert coding["duration_minutes"] == 90
    assert coding["difficulty_distribution"] == {"easy": 0.0, "medium": 1.0, "hard": 0.0}
    assert "requires_tpo_configuration" not in coding

    # Repeated recalculation is stable (no duplicated rounds/entries).
    third = _generate(tpo_headers, company, role)
    assert third["assessment_rounds"] == ["aptitude", "coding"]
    assert [e["round_type"] for e in third["tpo_configuration"]["rounds"]].count("coding") == 1
    assert third["round_patterns"]["coding"]["question_count"] == 40


def test_explicit_deselection_is_durable_and_distinguishable(tpo_headers):
    company, role = "PersistDeselectCo", "SDE"
    _add_complete_source(tpo_headers, company, role)
    before = _historical_count(tpo_headers)

    first = _generate(tpo_headers, company, role)
    assert first["assessment_rounds"] == ["aptitude", "coding"]
    assert first["evidence_rounds"] == ["aptitude", "coding"]

    deselected = _generate(tpo_headers, company, role, {"deselected_rounds": ["coding"]})
    # Effective view excludes the deselected round...
    assert deselected["assessment_rounds"] == ["aptitude"]
    # ... while pure evidence is preserved verbatim.
    assert deselected["evidence_rounds"] == ["aptitude", "coding"]
    coding_entry = next(e for e in deselected["tpo_configuration"]["rounds"] if e["round_type"] == "coding")
    assert coding_entry["enabled"] is False

    # Deselection survives a plain recalculation.
    recalc = _generate(tpo_headers, company, role)
    assert recalc["assessment_rounds"] == ["aptitude"]
    assert recalc["evidence_rounds"] == ["aptitude", "coding"]

    # Historical source records were never deleted.
    assert _historical_count(tpo_headers) == before


def test_absent_round_is_not_treated_as_deselected(tpo_headers):
    company, role = "AbsentNotDeselectedCo", "SDE"
    _add_complete_source(tpo_headers, company, role)

    # Deselect only aptitude; coding is merely unspecified, not deselected.
    result = _generate(tpo_headers, company, role, {"deselected_rounds": ["aptitude"]})
    assert result["assessment_rounds"] == ["coding"]
    round_types = {e["round_type"]: e for e in result["tpo_configuration"]["rounds"]}
    assert round_types["aptitude"]["enabled"] is False
    assert "coding" not in round_types  # unspecified -> evidence default, no entry

    # Re-selecting an evidence round clears the prior deselection.
    reselected = _generate(tpo_headers, company, role, {"added_rounds": ["aptitude"]})
    assert set(reselected["assessment_rounds"]) == {"aptitude", "coding"}


def test_legacy_pattern_without_tpo_configuration_loads_compatibly(tpo_headers):
    company, role = "LegacyPatternCo", "SDE"
    _add_complete_source(tpo_headers, company, role)
    _generate(tpo_headers, company, role)

    # Simulate a legacy persisted pattern that predates the durable config block.
    db = TestingSessionLocal()
    try:
        from app.models.company_data import CompanyPattern

        pattern = (
            db.query(CompanyPattern)
            .filter(CompanyPattern.company_name == company, CompanyPattern.target_role == role)
            .first()
        )
        data = dict(pattern.pattern_data)
        data.pop("tpo_configuration", None)
        pattern.pattern_data = data
        db.commit()
    finally:
        db.close()

    # Recalculation must not crash and must behave as evidence-only.
    recalc = _generate(tpo_headers, company, role)
    assert recalc["assessment_rounds"] == ["aptitude", "coding"]
    assert recalc["tpo_configuration"]["rounds"] == []
