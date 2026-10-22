"""
Route-level regression for the reported historical-document bug.

Reported scenario: a DOCX listing Aptitude, Coding, Software Engineering &
Design Patterns, Verbal Ability and SQL & Querying produced a Structured
Pattern whose Coding round had "no topics", and blueprint generation then
failed with 422 Unprocessable Content ("requires TPO configuration for topic
selection").

This test drives the real HTTP chain (upload -> pattern generate -> review ->
blueprint generate) and asserts the enriched Coding topics flow through the
blueprint. It is a separate file so it runs alone in its own process with a
fresh rate-limit window.
"""

import html
import io
import uuid
import zipfile

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


@pytest.fixture(scope="module")
def tpo_headers():
    uid = uuid.uuid4().hex[:8]
    email = f"blueprint_route_{uid}@test.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"name": "Test TPO", "email": email, "password": "Password@123", "role": "tpo"},
    )
    assert reg.status_code in (200, 201), f"Register failed: {reg.text}"
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "Password@123"})
    assert login.status_code == 200, f"Login failed: {login.text}"
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


HISTORICAL_URL = "/api/v1/tpo/company-data/historical"
PATTERN_URL = "/api/v1/tpo/company-data/pattern"
BLUEPRINT_URL = "/api/v1/tpo/company-data/blueprint"


def _upload_docx(headers: dict, company: str, role: str, body_text: str) -> None:
    docx_buf = io.BytesIO()
    with zipfile.ZipFile(docx_buf, "w") as z:
        paras = "".join(
            f"<w:p><w:r><w:t>{html.escape(line)}</w:t></w:r></w:p>"
            for line in body_text.strip().splitlines()
        )
        doc_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{paras}</w:body></w:document>"
        )
        z.writestr("word/document.xml", doc_xml)
    files = {"file": ("drive_experience.docx", io.BytesIO(docx_buf.getvalue()), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    res = client.post(
        f"{HISTORICAL_URL}/upload",
        data={"company_name": company, "target_role": role, "label": "Experience"},
        files=files,
        headers=headers,
    )
    assert res.status_code == 201, res.text


def test_reported_scenario_blueprint_generate_now_succeeds(tpo_headers):
    # The exact reported document shape: Aptitude + Coding rounds, with Verbal
    # Ability under Aptitude and engineering topics (Software Engineering &
    # Design Patterns, SQL & Querying) in the broader document context.
    _upload_docx(
        tpo_headers,
        "ReportedBugCo",
        "Software Engineer",
        "Selection Process 2024 - Software Engineer\n"
        "\n"
        "Round 1: Aptitude\n"
        "Verbal Ability, Quantitative Aptitude\n"
        "25 Questions\n"
        "35 Minutes\n"
        "\n"
        "Round 2: Coding\n"
        "2 Problems\n"
        "60 Minutes\n"
        "\n"
        "Job Requirements: Strong SQL & Querying. Good knowledge of Software Engineering & Design Patterns.\n"
        "Difficulty: Medium\n",
    )

    pattern_res = client.post(
        f"{PATTERN_URL}/generate",
        json={"company_name": "ReportedBugCo", "target_role": "Software Engineer"},
        headers=tpo_headers,
    )
    assert pattern_res.status_code == 200, pattern_res.text
    pdata = pattern_res.json()["pattern_data"]
    assert pdata["assessment_rounds"] == ["aptitude", "coding"]

    coding = pdata["round_patterns"]["coding"]
    assert set(coding.get("focus_areas") or []) == {
        "Software Engineering & Design Patterns",
        "SQL & Querying",
    }
    assert "requires_tpo_configuration" not in coding

    aptitude = pdata["round_patterns"]["aptitude"]
    assert "Verbal Ability" in (aptitude.get("focus_areas") or [])
    assert "requires_tpo_configuration" not in aptitude

    review = client.post(
        f"{PATTERN_URL}/ReportedBugCo/Software Engineer/review",
        json={"status": "approved"},
        headers=tpo_headers,
    )
    assert review.status_code == 200, review.text

    bp = client.post(
        f"{BLUEPRINT_URL}/generate",
        json={"company_name": "ReportedBugCo", "target_role": "Software Engineer"},
        headers=tpo_headers,
    )
    assert bp.status_code == 200, bp.text
    rounds = bp.json()["blueprint_data"]["rounds"]
    assert [r["round_type"] for r in rounds] == ["aptitude", "coding"]
    bp_coding = next(r for r in rounds if r["round_type"] == "coding")
    coding_topics = {t["topic"] for t in bp_coding["topics"]}
    assert {"Software Engineering & Design Patterns", "SQL & Querying"} <= coding_topics
    assert all(not t.get("is_default") for t in bp_coding["topics"])
    bp_aptitude = next(r for r in rounds if r["round_type"] == "aptitude")
    assert "Verbal Ability" in {t["topic"] for t in bp_aptitude["topics"]}


def test_evidence_round_plus_tpo_added_round_saves_reloads_and_generates(tpo_headers):
    # EDI5 reported workflow: evidence provides only Coding; the TPO adds an
    # Aptitude round with explicit numeric settings (no historical aptitude
    # topics exist) and saves. Reload must restore it and blueprint generation
    # must succeed using canonical default topics for the TPO-added round.
    _upload_docx(
        tpo_headers,
        "EdoiAddedCo",
        "Data Engineer",
        "Round 1: Coding\n"
        "Arrays, SQL & Querying\n"
        "2 Problems\n"
        "60 Minutes\n"
        "Difficulty: Medium\n",
    )

    pattern_res = client.post(
        f"{PATTERN_URL}/generate",
        json={"company_name": "EdoiAddedCo", "target_role": "Data Engineer"},
        headers=tpo_headers,
    )
    assert pattern_res.status_code == 200, pattern_res.text
    assert pattern_res.json()["pattern_data"]["assessment_rounds"] == ["coding"]

    # Before generation the blueprint simply does not exist yet (404 by contract).
    pre_lookup = client.get(f"{BLUEPRINT_URL}/EdoiAddedCo/Data Engineer", headers=tpo_headers)
    assert pre_lookup.status_code == 404, pre_lookup.text

    save = client.post(
        f"{PATTERN_URL}/generate",
        json={
            "company_name": "EdoiAddedCo",
            "target_role": "Data Engineer",
            "added_rounds": ["aptitude"],
            "round_configuration": [
                {
                    "round_type": "coding",
                    "question_count": 2,
                    "duration_minutes": 60,
                    "difficulty_distribution": {"easy": 0.0, "medium": 1.0, "hard": 0.0},
                },
                {
                    "round_type": "aptitude",
                    "question_count": 20,
                    "duration_minutes": 30,
                    "difficulty_distribution": {"easy": 0.25, "medium": 0.5, "hard": 0.25},
                },
            ],
        },
        headers=tpo_headers,
    )
    assert save.status_code == 200, save.text
    pdata = save.json()["pattern_data"]
    assert pdata["assessment_rounds"] == ["coding", "aptitude"]
    assert pdata["evidence_rounds"] == ["coding"]
    aptitude = pdata["round_patterns"]["aptitude"]
    assert aptitude["round_origin"] == "tpo_added"
    assert "requires_tpo_configuration" not in aptitude
    assert "focus_areas" not in aptitude

    # Recalculation/reload restores the durable TPO configuration unchanged.
    reload_res = client.post(
        f"{PATTERN_URL}/generate",
        json={"company_name": "EdoiAddedCo", "target_role": "Data Engineer"},
        headers=tpo_headers,
    )
    assert reload_res.status_code == 200, reload_res.text
    reloaded = reload_res.json()["pattern_data"]
    assert reloaded["assessment_rounds"] == ["coding", "aptitude"]
    assert reloaded["round_patterns"]["aptitude"]["round_origin"] == "tpo_added"
    assert "requires_tpo_configuration" not in reloaded["round_patterns"]["aptitude"]

    review = client.post(
        f"{PATTERN_URL}/EdoiAddedCo/Data Engineer/review",
        json={"status": "approved"},
        headers=tpo_headers,
    )
    assert review.status_code == 200, review.text

    bp = client.post(
        f"{BLUEPRINT_URL}/generate",
        json={"company_name": "EdoiAddedCo", "target_role": "Data Engineer"},
        headers=tpo_headers,
    )
    assert bp.status_code == 200, bp.text
    rounds = bp.json()["blueprint_data"]["rounds"]
    assert [r["round_type"] for r in rounds] == ["coding", "aptitude"]
    bp_aptitude = next(r for r in rounds if r["round_type"] == "aptitude")
    assert bp_aptitude["question_count"] == 20
    assert bp_aptitude["time_limit_minutes"] == 30
    assert bp_aptitude["topics"]
    assert all(t.get("is_default") for t in bp_aptitude["topics"])
    bp_coding = next(r for r in rounds if r["round_type"] == "coding")
    assert all(not t.get("is_default") for t in bp_coding["topics"])
