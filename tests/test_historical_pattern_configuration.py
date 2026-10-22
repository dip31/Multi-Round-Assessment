"""
Focused tests for the minimal historical-data assessment flow fix.

Covers:
 A. Section-scoped round extraction (numbered + named headings, named wins).
 B. Topic attribution priority: a round's own section first, then taxonomy
    attribution of global topics, then DETERMINISTIC contextual enrichment of
    orphaned same-document topics (e.g. Software Engineering & Design Patterns,
    SQL & Querying) into an already-detected round whose context matches. No
    round is ever added or removed by enrichment, and no topic outside the
    document is ever invented.
 C. No silent default-filling: missing per-round fields are left unset and the
    round is flagged ``requires_tpo_configuration``.
 D. Per-round difficulty deriving from source-level / round-level evidence.
 E. TPO round_configuration applied to evidence rounds only (unknown round => 422).
 F. Blueprint generation rejects flagged historical rounds with per-field errors.
 G. Explicit TPO config clears the flag and wins over evidence averages.
 H. Configuring count/duration/difficulty WITHOUT evidence topics still keeps the
    round flagged for topic selection.
 J. Same-document round context enrichment + the blueprint flow: doc-detect ->
    enrich -> blueprint rounds exactly match the document with enriched topics.
"""

import io
import html
import uuid
import zipfile
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.base import Base
from app.database.db import get_db
from app.main import app as application
from app.services.company_data_service import (
    _apply_added_rounds,
    _apply_round_configuration,
    _detect_round_heading,
    _extract_from_text,
    _extract_pattern_from_sources,
)
from app.services.company_blueprint_service import _compute_blueprint_rounds

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


# ── Helpers ───────────────────────────────────────────────────────────

def _register_and_login(role: str) -> dict:
    uid = uuid.uuid4().hex[:8]
    email = f"histconfig_{role}_{uid}@test.com"
    reg = client.post(
        "/api/v1/auth/register",
        json={"name": f"Test {role.capitalize()}", "email": email, "password": "Password@123", "role": role},
    )
    assert reg.status_code in (200, 201), f"Register failed for {role}: {reg.text}"
    login = client.post("/api/v1/auth/login", json={"email": email, "password": "Password@123"})
    assert login.status_code == 200, f"Login failed for {role}: {login.text}"
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.fixture(scope="module")
def tpo_headers():
    return _register_and_login("tpo")


BASE_HISTORICAL_URL = "/api/v1/tpo/company-data/historical"
BASE_PATTERN_URL = "/api/v1/tpo/company-data/pattern"
BASE_BLUEPRINT_URL = "/api/v1/tpo/company-data/blueprint"


def _add_source(headers: dict, company: str, role: str, raw_data: dict) -> None:
    res = client.post(
        BASE_HISTORICAL_URL,
        json={"company_name": company, "target_role": role, "label": "Evidence", "raw_data": raw_data},
        headers=headers,
    )
    assert res.status_code == 201, res.text


def _generate_pattern(headers: dict, company: str, role: str, body: dict = None) -> dict:
    res = client.post(
        f"{BASE_PATTERN_URL}/generate",
        json={"company_name": company, "target_role": role, **(body or {})},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    return res.json()["pattern_data"]


def _approve_and_generate_blueprint(headers: dict, company: str, role: str) -> dict:
    review = client.post(
        f"{BASE_PATTERN_URL}/{company}/{role}/review",
        json={"status": "approved"},
        headers=headers,
    )
    assert review.status_code == 200, review.text
    bp = client.post(
        f"{BASE_BLUEPRINT_URL}/generate",
        json={"company_name": company, "target_role": role},
        headers=headers,
    )
    return bp


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
        f"{BASE_HISTORICAL_URL}/upload",
        data={"company_name": company, "target_role": role, "label": "Experience"},
        files=files,
        headers=headers,
    )
    assert res.status_code == 201, res.text


# ── A. Section-scoped extraction ──────────────────────────────────────

def test_detect_round_heading_numbered_and_named():
    assert _detect_round_heading("Round 1: Aptitude (60 mins, 25 MCQs)") == "aptitude"
    assert _detect_round_heading("Stage 2 - Coding") == "coding"
    assert _detect_round_heading("Round 2: Technical Interview (45 mins)") == "technical_interview"
    assert _detect_round_heading("Aptitude Round") == "aptitude"
    # Bare named line without a round/stage marker is not a section heading.
    assert _detect_round_heading("HR Interview") is None
    assert _detect_round_heading("Round 3: HR Interview (30 mins)") == "hr_interview"
    assert _detect_round_heading("Coding Round (90 mins)") == "coding"
    assert _detect_round_heading("Topics: Arrays, Trees, Dynamic Programming.") is None
    assert _detect_round_heading("") is None
    assert _detect_round_heading("Overall difficulty level: hard.") is None
    # A bare numbered heading without a round NAME is not evidence of any round:
    # numbered position must never auto-inject aptitude/coding/technical.
    assert _detect_round_heading("Round 2") is None
    assert _detect_round_heading("Round 3: (45 mins)") is None
    assert _detect_round_heading("Stage 4") is None


def test_extract_from_text_attributes_topics_only_within_sections():
    text = (
        "Recruiter summary mentions Python and SQL as global skills only.\n"
        "Round 1: Aptitude (60 mins, 25 MCQs). Topics: Quantitative Aptitude, Logical Reasoning.\n"
        "Stage 2 - Coding (90 mins). Topics: Arrays, Dynamic Programming.\n"
        "Round 3: Technical Interview (45 mins). Topics: System Design, Operating Systems.\n"
    )
    data = _extract_from_text(text)
    rp = data["round_patterns"]

    assert "Quantitative Aptitude" in rp["aptitude"]["focus_areas"]
    assert "Logical Reasoning" in rp["aptitude"]["focus_areas"]
    assert "Arrays" in rp["coding"]["focus_areas"]
    assert "Dynamic Programming" in rp["coding"]["focus_areas"]
    assert "System Design" in rp["technical_interview"]["focus_areas"]
    assert "Operating Systems" in rp["technical_interview"]["focus_areas"]

    # Global-only mentions must NOT leak into round-scoped focus areas.
    for round_key in ("aptitude", "coding", "technical_interview"):
        assert "Python" not in rp[round_key]["focus_areas"]
        assert "SQL & Querying" not in rp[round_key]["focus_areas"]
    # ... but they do remain document-level topics.
    assert "Python" in data["topics"]
    assert "SQL & Querying" in data["topics"]

    # Section durations/counts captured per section, first occurrence wins.
    assert rp["aptitude"]["duration_minutes"] == 60
    assert rp["aptitude"]["question_count"] == 25


def test_named_heading_overrides_numbered_default_in_round_patterns(tpo_headers):
    _upload_docx(
        tpo_headers,
        "AlphaCorp",
        "Software Engineer",
        (
            "AlphaCorp 2024\n"
            "Round 1: Aptitude (45 mins, 25 questions). Topics: Logical Reasoning.\n"
            "Round 2: Technical Interview (45 mins). Topics: System Design.\n"
            "Round 3: HR Round (30 mins). Topics: Behavioral & Leadership Principles.\n"
        ),
    )
    pdata = _generate_pattern(tpo_headers, "AlphaCorp", "Software Engineer")
    rp = pdata["round_patterns"]
    # Round 2 is named explicitly as a Technical Interview => technical_interview,
    # NOT the numbered-default coding round.
    assert pdata["assessment_rounds"] == ["aptitude", "technical_interview", "hr_interview"]
    assert "technical_interview" in rp
    assert "System Design" in rp["technical_interview"]["focus_areas"]
    assert "coding" not in rp


# ── B/C/D. No defaults, marker + per-round difficulty ─────────────────

def test_missing_round_fields_flagged_and_not_default_filled(tpo_headers):
    _add_source(
        tpo_headers,
        "SparseCo",
        "Software Engineer",
        {
            "rounds": ["aptitude", "coding"],
            "topics": ["SQL", "Operating Systems"],
            "difficulty": "hard",
        },
    )
    pdata = _generate_pattern(tpo_headers, "SparseCo", "Software Engineer")
    rp = pdata["round_patterns"]

    aptitude = rp["aptitude"]
    # No silent default count/duration/focus.
    assert "avg_duration_minutes" not in aptitude
    assert "avg_question_count" not in aptitude
    assert "focus_areas" not in aptitude
    assert aptitude["requires_tpo_configuration"] is True
    # Source-level difficulty IS explicit evidence -> per-round distribution set.
    assert aptitude["difficulty_distribution"] == {"easy": 0.0, "medium": 0.0, "hard": 1.0}

    coding = rp["coding"]
    # The document's engineering context (SQL & Querying, Operating Systems)
    # is now contextually enriched into the detected Coding round instead of
    # being dropped; count/duration are still genuinely absent -> still flagged.
    assert set(coding["focus_areas"]) == {"SQL & Querying", "Operating Systems"}
    assert coding["requires_tpo_configuration"] is True


def test_round_level_difficulty_and_partial_marker(tpo_headers):
    _add_source(
        tpo_headers,
        "RoundDiffCo",
        "SDE",
        {
            "rounds": ["coding", "hr_interview"],
            "topics": ["Data Structures & Algorithms", "Behavioral & Leadership Principles"],
            "round_patterns": {
                "coding": {
                    "duration_minutes": 90,
                    "question_count": 2,
                    "focus_areas": ["Data Structures & Algorithms"],
                    "difficulty": "hard",
                },
                "hr_interview": {
                    "duration_minutes": 30,
                    "focus_areas": ["Behavioral & Leadership Principles"],
                    "difficulty": "medium",
                },
            },
        },
    )
    pdata = _generate_pattern(tpo_headers, "RoundDiffCo", "SDE")
    rp = pdata["round_patterns"]

    assert rp["coding"]["difficulty_distribution"] == {"easy": 0.0, "medium": 0.0, "hard": 1.0}
    assert "requires_tpo_configuration" not in rp["coding"]

    assert rp["hr_interview"]["difficulty_distribution"] == {"easy": 0.0, "medium": 1.0, "hard": 0.0}
    assert rp["hr_interview"]["requires_tpo_configuration"] is True  # question count missing


def test_no_difficulty_evidence_leaves_distribution_unset(tpo_headers):
    _add_source(
        tpo_headers,
        "NoDiffCo",
        "Analyst",
        {
            "rounds": ["aptitude"],
            "topics": ["Data Interpretation"],
            "round_patterns": {"aptitude": {"duration_minutes": 45, "question_count": 20, "focus_areas": ["Data Interpretation"]}},
        },
    )
    pdata = _generate_pattern(tpo_headers, "NoDiffCo", "Analyst")
    rp = pdata["round_patterns"]["aptitude"]
    assert "difficulty_distribution" not in rp
    assert rp["requires_tpo_configuration"] is True


# ── E. TPO round_configuration ────────────────────────────────────────

def test_round_configuration_applied_and_clears_flag(tpo_headers):
    _add_source(
        tpo_headers,
        "ConfiguredFlowCo",
        "SDE",
        {
            "rounds": ["coding"],
            "topics": ["Arrays", "Dynamic Programming"],
            "round_patterns": {"coding": {"duration_minutes": 45, "question_count": 5, "focus_areas": ["Arrays", "Dynamic Programming"]}},
            "difficulty": "hard",
        },
    )
    pdata = _generate_pattern(
        tpo_headers,
        "ConfiguredFlowCo",
        "SDE",
        {
            "round_configuration": [
                {
                    "round_type": "coding",
                    "question_count": 40,
                    "duration_minutes": 90,
                    "difficulty_distribution": {"easy": 0.0, "medium": 0.5, "hard": 0.5},
                }
            ]
        },
    )
    rp = pdata["round_patterns"]["coding"]
    assert rp["question_count"] == 40
    assert rp["duration_minutes"] == 90
    assert rp["difficulty_distribution"] == {"easy": 0.0, "medium": 0.5, "hard": 0.5}
    assert "requires_tpo_configuration" not in rp

    bp = _approve_and_generate_blueprint(tpo_headers, "ConfiguredFlowCo", "SDE")
    assert bp.status_code == 200, bp.text
    coding_round = next(r for r in bp.json()["blueprint_data"]["rounds"] if r["round_type"] == "coding")
    # Explicit TPO config wins over the evidence average (5 questions / 45 mins).
    assert coding_round["question_count"] == 40
    assert coding_round["time_limit_minutes"] == 90


def test_round_configuration_rejects_round_not_in_evidence(tpo_headers):
    _add_source(
        tpo_headers,
        "UnsupportedRoundCo",
        "Engineer",
        {"rounds": ["coding"], "topics": ["Arrays"]},
    )
    res = client.post(
        f"{BASE_PATTERN_URL}/generate",
        json={
            "company_name": "UnsupportedRoundCo",
            "target_role": "Engineer",
            "round_configuration": [
                {"round_type": "aptitude", "question_count": 20, "duration_minutes": 45, "difficulty_distribution": {"easy": 1, "medium": 0, "hard": 0}}
            ],
        },
        headers=tpo_headers,
    )
    assert res.status_code == 422
    assert "not present" in res.json()["detail"]


def test_round_configuration_schema_rejects_incomplete_round(tpo_headers):
    _add_source(
        tpo_headers,
        "IncompleteConfigCo",
        "Engineer",
        {"rounds": ["coding"], "topics": ["Arrays"]},
    )
    res = client.post(
        f"{BASE_PATTERN_URL}/generate",
        json={
            "company_name": "IncompleteConfigCo",
            "target_role": "Engineer",
            "round_configuration": [
                {"round_type": "coding", "duration_minutes": 90, "difficulty_distribution": {"easy": 1, "medium": 0, "hard": 0}}
            ],
        },
        headers=tpo_headers,
    )
    assert res.status_code == 422


def test_round_configuration_schema_rejects_invalid_weights(tpo_headers):
    _add_source(
        tpo_headers,
        "BadWeightsCo",
        "Engineer",
        {"rounds": ["coding"], "topics": ["Arrays"]},
    )
    res = client.post(
        f"{BASE_PATTERN_URL}/generate",
        json={
            "company_name": "BadWeightsCo",
            "target_role": "Engineer",
            "round_configuration": [
                {"round_type": "coding", "question_count": 2, "duration_minutes": 90, "difficulty_distribution": {"easy": 0.7, "medium": 0.7, "hard": 0.0}}
            ],
        },
        headers=tpo_headers,
    )
    assert res.status_code == 422


# ── F. Blueprint validation ───────────────────────────────────────────

def test_blueprint_rejects_flagged_round_with_per_field_errors(tpo_headers):
    _add_source(
        tpo_headers,
        "IncompleteEvCo",
        "SDE",
        {
            "rounds": ["aptitude"],
            "topics": ["Quantitative Aptitude"],
            "round_patterns": {"aptitude": {"duration_minutes": 60, "focus_areas": ["Quantitative Aptitude"]}},
            "difficulty": "medium",
        },
    )
    pdata = _generate_pattern(tpo_headers, "IncompleteEvCo", "SDE")
    assert pdata["round_patterns"]["aptitude"]["requires_tpo_configuration"] is True

    bp = _approve_and_generate_blueprint(tpo_headers, "IncompleteEvCo", "SDE")
    assert bp.status_code == 422
    assert "requires TPO configuration for question count" in bp.json()["detail"]


def test_blueprint_rejects_missing_topic_selection_even_after_config(tpo_headers):
    # Round has no evidence-backed focus/topics at all; configuring the
    # numeric fields must NOT silently default the topic selection.
    _add_source(
        tpo_headers,
        "NoTopicsCo",
        "SDE",
        {"rounds": ["aptitude"], "topics": ["System Design"], "difficulty": "medium"},
    )
    _generate_pattern(
        tpo_headers,
        "NoTopicsCo",
        "SDE",
        {
            "round_configuration": [
                {"round_type": "aptitude", "question_count": 20, "duration_minutes": 45, "difficulty_distribution": {"easy": 0.5, "medium": 0.5, "hard": 0.0}}
            ]
        },
    )
    bp = _approve_and_generate_blueprint(tpo_headers, "NoTopicsCo", "SDE")
    assert bp.status_code == 422
    assert "requires TPO configuration for topic selection" in bp.json()["detail"]


def test_blueprint_succeeds_after_full_evidence_and_tpo_config(tpo_headers):
    _add_source(
        tpo_headers,
        "CompleteFlowCo",
        "Engineer",
        {
            "rounds": ["coding"],
            "topics": ["Arrays", "Dynamic Programming"],
            "round_patterns": {"coding": {"duration_minutes": 45, "question_count": 5, "focus_areas": ["Arrays", "Dynamic Programming"]}},
            "difficulty": "hard",
        },
    )
    pdata = _generate_pattern(
        tpo_headers,
        "CompleteFlowCo",
        "Engineer",
        {
            "round_configuration": [
                {"round_type": "coding", "question_count": 40, "duration_minutes": 90, "difficulty_distribution": {"easy": 0.0, "medium": 1.0, "hard": 0.0}}
            ]
        },
    )
    assert "requires_tpo_configuration" not in pdata["round_patterns"]["coding"]

    bp = _approve_and_generate_blueprint(tpo_headers, "CompleteFlowCo", "Engineer")
    assert bp.status_code == 200, bp.text
    rounds = bp.json()["blueprint_data"]["rounds"]
    assert len(rounds) == 1
    assert rounds[0]["round_type"] == "coding"
    assert rounds[0]["question_count"] == 40
    assert rounds[0]["time_limit_minutes"] == 90
    assert rounds[0]["difficulty_distribution"] == {"easy": 0.0, "medium": 1.0, "hard": 0.0}
    assert [t["topic"] for t in rounds[0]["topics"]] == ["Arrays", "Dynamic Programming"]


# ── G. TPO-selected topic persistence (audit fix) ──────────────────────

def test_tpo_selects_evidence_coding_topics_persist_and_unblock(tpo_headers):
    # Evidence contains Coding-attributed topics; the round is flagged only
    # because question count/duration are missing. TPO explicitly selects a
    # subset -> persisted into focus_areas (overriding the evidence-derived
    # set), marker cleared, blueprint succeeds.
    _add_source(
        tpo_headers,
        "TopicSelectCo",
        "Engineer",
        {
            "rounds": ["coding"],
            "topics": ["Arrays", "Dynamic Programming"],
            "difficulty": "hard",
        },
    )
    pdata = _generate_pattern(
        tpo_headers,
        "TopicSelectCo",
        "Engineer",
        {
            "round_configuration": [
                {
                    "round_type": "coding",
                    "question_count": 40,
                    "duration_minutes": 90,
                    "difficulty_distribution": {"easy": 0.0, "medium": 1.0, "hard": 0.0},
                    "focus_areas": ["Arrays"],
                }
            ]
        },
    )
    rp = pdata["round_patterns"]["coding"]
    assert rp["focus_areas"] == ["Arrays"]
    assert "requires_tpo_configuration" not in rp

    bp = _approve_and_generate_blueprint(tpo_headers, "TopicSelectCo", "Engineer")
    assert bp.status_code == 200, bp.text
    coding_round = next(r for r in bp.json()["blueprint_data"]["rounds"] if r["round_type"] == "coding")
    assert coding_round["question_count"] == 40
    assert "Arrays" in [t["topic"] for t in coding_round["topics"]]


def test_no_coding_evidence_round_remains_blocked_and_rejects_cross_round_topics(tpo_headers):
    # Barclays-like: the only evidence topic is Verbal Ability (typical_round
    # aptitude), so nothing is selectable for Coding. Numeric-only config keeps
    # the flag; blueprints keep 422ing on topic selection.
    _add_source(
        tpo_headers,
        "BarclaysLikeCo",
        "Product manager",
        {
            "rounds": ["coding"],
            "topics": ["Verbal Ability"],
            "difficulty": "hard",
        },
    )
    pdata = _generate_pattern(
        tpo_headers,
        "BarclaysLikeCo",
        "Product manager",
        {
            "round_configuration": [
                {"round_type": "coding", "question_count": 5, "duration_minutes": 35, "difficulty_distribution": {"easy": 0.0, "medium": 0.0, "hard": 1.0}}
            ]
        },
    )
    coding = pdata["round_patterns"]["coding"]
    assert coding["requires_tpo_configuration"] is True
    assert "focus_areas" not in coding

    bp = _approve_and_generate_blueprint(tpo_headers, "BarclaysLikeCo", "Product manager")
    assert bp.status_code == 422
    assert "requires TPO configuration for topic selection" in bp.json()["detail"]

    # Trying to select the aptitude topic for Coding is rejected.
    res = client.post(
        f"{BASE_PATTERN_URL}/generate",
        json={
            "company_name": "BarclaysLikeCo",
            "target_role": "Product manager",
            "round_configuration": [
                {"round_type": "coding", "question_count": 5, "duration_minutes": 35, "difficulty_distribution": {"easy": 1, "medium": 0, "hard": 0}, "focus_areas": ["Verbal Ability"]}
            ],
        },
        headers=tpo_headers,
    )
    assert res.status_code == 422
    assert "'Verbal Ability' cannot be selected for round 'coding'" in res.json()["detail"]


def test_document_supported_cross_round_topics_selectable_for_coding(tpo_headers):
    # SQL & Querying and Software Engineering & Design Patterns have taxonomy
    # typical_round=technical_interview, but this document detected only Coding
    # and contains those engineering topics. Contextual enrichment attaches them
    # to Coding; the TPO may therefore (re)select them for Coding, and the
    # resulting pattern feeds blueprint computation directly (the 422 fix lives
    # at the data layer).
    _add_source(
        tpo_headers,
        "CrossRoundCo",
        "Engineer",
        {
            "rounds": ["coding"],
            "topics": ["SQL & Querying", "Software Engineering & Design Patterns"],
            "difficulty": "medium",
        },
    )
    res = client.post(
        f"{BASE_PATTERN_URL}/generate",
        json={
            "company_name": "CrossRoundCo",
            "target_role": "Engineer",
            "round_configuration": [
                {"round_type": "coding", "question_count": 2, "duration_minutes": 90, "difficulty_distribution": {"easy": 1, "medium": 0, "hard": 0}, "focus_areas": ["SQL & Querying", "Software Engineering & Design Patterns"]}
            ],
        },
        headers=tpo_headers,
    )
    assert res.status_code == 200, res.text
    pdata = res.json()["pattern_data"]
    coding = pdata["round_patterns"]["coding"]
    assert set(coding["focus_areas"]) == {"SQL & Querying", "Software Engineering & Design Patterns"}
    assert "requires_tpo_configuration" not in coding

    computed = _compute_blueprint_rounds(pdata)
    bp_coding = next(r for r in computed if r["round_type"] == "coding")
    assert {"SQL & Querying", "Software Engineering & Design Patterns"} <= {t["topic"] for t in bp_coding["topics"]}
    assert all(not t["is_default"] for t in bp_coding["topics"])

    # Service-level counter-case: a topic the document never mentioned for this
    # round is still rejected even after enrichment (no fabrication).
    with pytest.raises(Exception) as exc:
        _apply_round_configuration(
            pdata,
            [
                {
                    "round_type": "coding",
                    "question_count": 2,
                    "duration_minutes": 90,
                    "difficulty_distribution": {"easy": 1, "medium": 0, "hard": 0},
                    "focus_areas": ["Arrays"],
                }
            ],
        )
    assert "Arrays" in str(exc.value)


def test_configuration_without_focus_areas_preserves_existing_behavior(tpo_headers):
    # Legacy configs omit focus_areas entirely; evidence-derived focus_areas
    # must be preserved untouched and the marker cleared exactly as before.
    _add_source(
        tpo_headers,
        "LegacyConfigCo",
        "Engineer",
        {
            "rounds": ["coding"],
            "topics": ["Arrays", "Dynamic Programming"],
            "difficulty": "hard",
            "round_patterns": {"coding": {"focus_areas": ["Arrays", "Dynamic Programming"]}},
        },
    )
    pdata = _generate_pattern(
        tpo_headers,
        "LegacyConfigCo",
        "Engineer",
        {
            "round_configuration": [
                {"round_type": "coding", "question_count": 40, "duration_minutes": 90, "difficulty_distribution": {"easy": 0.0, "medium": 1.0, "hard": 0.0}}
            ]
        },
    )
    rp = pdata["round_patterns"]["coding"]
    assert set(rp["focus_areas"]) == {"Arrays", "Dynamic Programming"}
    assert "requires_tpo_configuration" not in rp


# ── I. No invented rounds; explicit TPO-added rounds ────────────────

class _FakeSource:
    """Minimal duck-typed historical source for service-level aggregation tests."""

    def __init__(self, sid: int, raw_data: dict):
        self.id = sid
        self.raw_data = raw_data
        self.source_type = "file_upload"
        self.label = "Evidence"
        self.file_name = None


def test_report_aptitude_document_with_problem_solving_does_not_inject_coding():
    # Quant aptitude descriptions commonly say "problem solving" (generic).
    # It is NOT coding evidence, and must not add a Coding round.
    raw = _extract_from_text(
        "Round 1: Aptitude Test\nQuantitative Aptitude and Problem Solving\n25 Questions\n30 minutes"
    )
    assert raw["rounds"] == ["aptitude"]
    pdata = _extract_pattern_from_sources([_FakeSource(1, raw)])
    assert pdata["assessment_rounds"] == ["aptitude"]
    assert "coding" not in pdata["round_patterns"]


def test_unnamed_numbered_heading_injects_no_phantom_round():
    raw = _extract_from_text(
        "Round 1: Aptitude\n50 Questions\nRound 2\n20 Questions"
    )
    assert raw.get("rounds") == ["aptitude"]
    pdata = _extract_pattern_from_sources([_FakeSource(1, raw)])
    assert pdata["assessment_rounds"] == ["aptitude"]
    assert "coding" not in pdata["round_patterns"]


def test_no_rounds_detected_yields_empty_assessment_rounds_not_defaults():
    raw = _extract_from_text("This document covers company policy, insurance and leave benefits only.")
    pdata = _extract_pattern_from_sources([_FakeSource(1, raw)])
    assert pdata["assessment_rounds"] == []
    assert pdata["round_patterns"] == {}


def test_evidence_derived_rounds_are_tagged_evidence_origin():
    raw = _extract_from_text("Round 1: Aptitude Test\nVerbal Ability\n20 Questions\n30 minutes")
    pdata = _extract_pattern_from_sources([_FakeSource(1, raw)])
    assert pdata["assessment_rounds"] == ["aptitude"]
    assert pdata["round_patterns"]["aptitude"]["round_origin"] == "evidence"


def test_cross_round_topics_contextually_enriched_not_randomly_attributed():
    # SQL & Querying belongs to technical_interview by taxonomy, but this
    # document detected only Coding and references SQL in its Coding context.
    # Contextual enrichment adds it to Coding (same document support) while an
    # unrelated topic (e.g. Verbal Ability) is never pulled in.
    raw = _extract_from_text(
        "Round 1: Coding\nTopics: Python, SQL & Querying\n2 Problems\n60 Minutes"
    )
    pdata = _extract_pattern_from_sources([_FakeSource(1, raw)])
    assert pdata["assessment_rounds"] == ["coding"]
    focus = pdata["round_patterns"]["coding"].get("focus_areas") or []
    assert "Python" in focus
    assert "SQL & Querying" in focus
    assert "Verbal Ability" not in focus


def test_blueprint_computation_never_pads_with_default_rounds():
    assert _compute_blueprint_rounds({}) == []
    assert _compute_blueprint_rounds({"assessment_rounds": []}) == []
    computed = _compute_blueprint_rounds({"assessment_rounds": ["aptitude"]})
    assert [r["round_type"] for r in computed] == ["aptitude"]


def test_tpo_added_round_without_evidence_topics_is_complete_and_uses_defaults():
    # The TPO explicitly adds Coding and fills count/duration/difficulty. There
    # is no coding-topic evidence to select from, but the round is a deliberate
    # TPO choice, so it is complete and the blueprint derives the canonical
    # default Coding topics (marked as defaults) instead of blocking.
    raw = _extract_from_text(
        "Round 1: Aptitude Test\nQuantitative Aptitude\n25 Questions\n30 minutes\nDifficulty: medium"
    )
    pdata = _extract_pattern_from_sources([_FakeSource(1, raw)])
    pdata = _apply_added_rounds(pdata, ["coding"])
    pdata = _apply_round_configuration(
        pdata,
        [
            {"round_type": "coding", "question_count": 2, "duration_minutes": 60, "difficulty_distribution": {"easy": 0.0, "medium": 0.5, "hard": 0.5}}
        ],
    )
    coding = pdata["round_patterns"]["coding"]
    assert coding["round_origin"] == "tpo_added"
    assert "requires_tpo_configuration" not in coding
    assert "focus_areas" not in coding

    computed = _compute_blueprint_rounds(pdata)
    coding_bp = next(r for r in computed if r["round_type"] == "coding")
    assert coding_bp["question_count"] == 2
    assert coding_bp["time_limit_minutes"] == 60
    assert coding_bp["topics"]
    assert all(t["is_default"] for t in coding_bp["topics"])


def test_tpo_added_round_without_numeric_config_is_still_blocked():
    # A TPO-added round with no numeric settings is genuinely incomplete and must
    # keep failing with an actionable 422 rather than silently using defaults.
    raw = _extract_from_text(
        "Round 1: Aptitude Test\nQuantitative Aptitude\n25 Questions\n30 minutes\nDifficulty: medium"
    )
    pdata = _extract_pattern_from_sources([_FakeSource(1, raw)])
    pdata = _apply_added_rounds(pdata, ["coding"])
    coding = pdata["round_patterns"]["coding"]
    assert coding["round_origin"] == "tpo_added"
    assert coding["requires_tpo_configuration"] is True
    with pytest.raises(HTTPException) as exc:
        _compute_blueprint_rounds(pdata)
    assert exc.value.status_code == 422
    assert "requires TPO configuration" in exc.value.detail


def test_reported_bug_aptitude_docx_end_to_end_has_no_coding(tpo_headers):
    # End-to-end repro of the reported bug: an Aptitude-only document (with the
    # common "problem solving" phrasing) previously produced "2 Sequential
    # Rounds: Aptitude, Coding". It must now produce only Aptitude.
    _upload_docx(
        tpo_headers,
        "ProblemSolvingCo",
        "Software Engineer",
        "Selection Process 2024:\n"
        "Round 1: Aptitude\n"
        "Quantitative Aptitude, Logical Reasoning and Problem Solving\n"
        "25 Questions\n"
        "35 Minutes\n"
        "Difficulty: Hard",
    )
    pdata = _generate_pattern(tpo_headers, "ProblemSolvingCo", "Software Engineer")
    assert pdata["assessment_rounds"] == ["aptitude"]
    assert "coding" not in pdata["round_patterns"]


def test_coding_python_document_produces_only_coding():
    # Counter-example from the bug report: Coding + Python docs must resolve to
    # exactly one Coding round; Aptitude is never added automatically.
    raw = _extract_from_text(
        "Round 1: Coding\nProgramming skills: Python, Data Structures\n2 Problems\n60 Minutes"
    )
    pdata = _extract_pattern_from_sources([_FakeSource(1, raw)])
    assert pdata["assessment_rounds"] == ["coding"]
    assert "aptitude" not in pdata["assessment_rounds"]
    focus = pdata["round_patterns"]["coding"].get("focus_areas") or []
    assert "Python" in focus


def test_service_level_added_rounds_preserve_evidence_origin():
    raw = _extract_from_text("Round 1: Aptitude\nQuantitative Aptitude\n20 Questions\n30 minutes")
    pdata = _extract_pattern_from_sources([_FakeSource(1, raw)])
    pdata = _apply_added_rounds(pdata, ["coding", "hr_interview"])
    assert pdata["assessment_rounds"] == ["aptitude", "coding", "hr_interview"]
    assert pdata["round_patterns"]["aptitude"]["round_origin"] == "evidence"
    assert pdata["round_patterns"]["coding"]["round_origin"] == "tpo_added"
    assert pdata["round_patterns"]["hr_interview"]["round_origin"] == "tpo_added"
    assert pdata["round_patterns"]["coding"]["requires_tpo_configuration"] is True
    # Adding an already-present evidence round is a no-op and never downgrades it.
    pdata = _apply_added_rounds(pdata, ["aptitude"])
    assert pdata["assessment_rounds"] == ["aptitude", "coding", "hr_interview"]
    assert pdata["round_patterns"]["aptitude"]["round_origin"] == "evidence"


# ── J. Same-document round context enrichment & the blueprint flow ────

def test_document_aptitude_coding_produces_exactly_two_rounds():
    # Test case 1: Aptitude + Coding -> exactly Aptitude + Coding.
    raw = _extract_from_text(
        "Round 1: Aptitude (25 questions, 35 minutes)\n"
        "Round 2: Coding (2 problems, 60 minutes)"
    )
    pdata = _extract_pattern_from_sources([_FakeSource(1, raw)])
    assert pdata["assessment_rounds"] == ["aptitude", "coding"]
    assert set(pdata["round_patterns"]) == {"aptitude", "coding"}
    assert "technical_interview" not in pdata["assessment_rounds"]
    assert "hr_interview" not in pdata["assessment_rounds"]


def test_document_aptitude_coding_interview_produces_exactly_three():
    # Test case 2: Aptitude + Coding + Technical Interview -> exactly those.
    raw = _extract_from_text(
        "Round 1: Aptitude Test\nRound 2: Coding Round\nRound 3: Technical Interview (System Design)"
    )
    pdata = _extract_pattern_from_sources([_FakeSource(1, raw)])
    assert pdata["assessment_rounds"] == ["aptitude", "coding", "technical_interview"]
    assert "hr_interview" not in pdata["assessment_rounds"]


def test_document_only_aptitude_stays_only_aptitude():
    # Test case 3: ONLY Aptitude -> never Coding/Interview, even for an engineer role.
    raw = _extract_from_text(
        "Aptitude Test\nVerbal Ability, Logical Reasoning\n20 questions\n30 minutes"
    )
    pdata = _extract_pattern_from_sources([_FakeSource(1, raw)])
    assert pdata["assessment_rounds"] == ["aptitude"]
    assert set(pdata["round_patterns"]) == {"aptitude"}


def test_coding_enriched_from_broader_document_context():
    # Test case 6: Coding has no topic heading of its own; the broader
    # requirements/JD in the SAME document support Coding topics.
    raw = _extract_from_text(
        "Round 1: Coding\n2 problems, 60 minutes\n\n"
        "Requirements: SQL & Querying, Software Engineering & Design Patterns"
    )
    pdata = _extract_pattern_from_sources([_FakeSource(1, raw)])
    assert pdata["assessment_rounds"] == ["coding"]
    focus = pdata["round_patterns"]["coding"].get("focus_areas") or []
    assert "SQL & Querying" in focus
    assert "Software Engineering & Design Patterns" in focus


def test_normalized_evidence_attributed_to_supported_rounds_only():
    # Test case 7: normalized evidence = SE&DP + Verbal Ability + SQL & Querying
    # with detected rounds Aptitude + Coding. Aptitude holds Verbal Ability,
    # Coding holds the engineering context, and nothing leaks across.
    raw = _extract_from_text(
        "Aptitude\nVerbal Ability\n\nCoding\n\n"
        "Software Engineering & Design Patterns\nSQL & Querying"
    )
    pdata = _extract_pattern_from_sources([_FakeSource(1, raw)])
    assert pdata["assessment_rounds"] == ["aptitude", "coding"]
    aptitude_focus = pdata["round_patterns"]["aptitude"].get("focus_areas") or []
    coding_focus = pdata["round_patterns"]["coding"].get("focus_areas") or []
    assert "Verbal Ability" in aptitude_focus
    assert "Software Engineering & Design Patterns" in coding_focus
    assert "SQL & Querying" in coding_focus
    assert "Verbal Ability" not in coding_focus
    assert not (set(aptitude_focus) & {"Software Engineering & Design Patterns", "SQL & Querying"})


def test_rounds_stay_exact_and_topics_never_invented():
    # Test cases 8/9 analog: enrichment of already-detected rounds must never
    # add/remove a round, and must never invent a topic the document lacks.
    raw = _extract_from_text("Aptitude\nVerbal Ability\nCoding\nPython")
    detected_before = list(raw.get("rounds", []))
    pdata = _extract_pattern_from_sources([_FakeSource(1, raw)])
    assert pdata["assessment_rounds"] == detected_before
    assert set(pdata["round_patterns"]) == set(detected_before)
    assert "technical_interview" not in pdata["assessment_rounds"]
    doc_topics = set(pdata["topics"])
    for rp in pdata["round_patterns"].values():
        for topic in (rp.get("focus_areas") or []):
            assert topic in doc_topics


def test_blueprint_rounds_derived_from_document_rounds_and_topics():
    # Test cases 10/12 (service layer): the blueprint 422 was caused by the
    # flagged Coding round (no topics). With enrichment the round is complete
    # and blueprint computation uses exactly the document's rounds + topics.
    pattern_data = _extract_pattern_from_sources(
        [
            _FakeSource(
                1,
                {
                    "rounds": ["aptitude", "coding"],
                    "topics": ["Verbal Ability", "SQL & Querying", "Software Engineering & Design Patterns"],
                    "round_patterns": {
                        "aptitude": {"duration_minutes": 35, "question_count": 25, "focus_areas": ["Verbal Ability"]},
                        "coding": {"duration_minutes": 60, "question_count": 2},
                    },
                    "difficulty": "medium",
                },
            )
        ]
    )
    assert "requires_tpo_configuration" not in pattern_data["round_patterns"]["coding"]
    computed = _compute_blueprint_rounds(pattern_data)
    assert [round_cfg["round_type"] for round_cfg in computed] == ["aptitude", "coding"]
    coding_bp = next(round_cfg for round_cfg in computed if round_cfg["round_type"] == "coding")
    coding_topics = {topic["topic"] for topic in coding_bp["topics"]}
    assert {"SQL & Querying", "Software Engineering & Design Patterns"} <= coding_topics
    assert all(not topic["is_default"] for topic in coding_bp["topics"])
    aptitude_bp = next(round_cfg for round_cfg in computed if round_cfg["round_type"] == "aptitude")
    aptitude_topics = {topic["topic"] for topic in aptitude_bp["topics"]}
    assert "Verbal Ability" in aptitude_topics
    assert not (aptitude_topics & coding_topics)


def test_historical_blueprint_succeeds_for_valid_rich_document():
    # Test cases 10/11/12: the exact scenario that returned 422 on
    # POST /tpo/company-data/blueprint/generate (Coding round flagged because
    # its topics were stranded under technical_interview taxonomy). The 422 is
    # raised by _compute_blueprint_rounds at the data layer, so this validates
    # the fix at that layer: an Aptitude+Coding document with engineering
    # context yields a complete, un-flagged pattern and a blueprint whose
    # rounds exactly match the document, with enriched (non-default) topics.
    raw = _extract_from_text(
        "Round 1: Aptitude\n"
        "Verbal Ability, Quantitative Aptitude\n"
        "25 questions\n"
        "35 minutes\n"
        "\n"
        "Round 2: Coding\n"
        "2 problems\n"
        "60 minutes\n"
        "Difficulty: Medium\n"
        "\n"
        "Requirements: SQL & Querying, Software Engineering & Design Patterns\n"
    )
    pdata = _extract_pattern_from_sources([_FakeSource(1, raw)])
    assert pdata["assessment_rounds"] == ["aptitude", "coding"]
    for rp in pdata["round_patterns"].values():
        assert "requires_tpo_configuration" not in rp, rp

    computed = _compute_blueprint_rounds(pdata)
    assert [r["round_type"] for r in computed] == ["aptitude", "coding"]
    coding_bp = next(r for r in computed if r["round_type"] == "coding")
    coding_topics = {t["topic"] for t in coding_bp["topics"]}
    assert "SQL & Querying" in coding_topics
    assert "Software Engineering & Design Patterns" in coding_topics
    assert all(not t["is_default"] for t in coding_bp["topics"])
    aptitude_bp = next(r for r in computed if r["round_type"] == "aptitude")
    assert "Verbal Ability" in {t["topic"] for t in aptitude_bp["topics"]}


def test_question_pool_spec_uses_blueprint_round_specific_topics():
    # Test case 13: pool generation consumes each blueprint round's OWN topics;
    # Coding questions use Coding context (SE/SQL), Aptitude questions use
    # Verbal Ability; no cross-round bleed.
    from app.services.question_pool_generation_service import QuestionPoolGenerationService

    bp_data = {
        "rounds": [
            {"round_type": "aptitude", "topics": [{"topic": "Verbal Ability", "weight_pct": 100.0}]},
            {"round_type": "coding", "topics": [{"topic": "SQL & Querying", "weight_pct": 50.0}, {"topic": "Software Engineering & Design Patterns", "weight_pct": 50.0}]},
        ]
    }

    class _BP:
        company_name = "X"
        target_role = "Y"
        status = "approved"

    svc = QuestionPoolGenerationService(llm_generator=object())
    apt_spec = svc._build_spec(_BP(), {"blueprint_data": bp_data}, "aptitude", bp_data["rounds"][0], 10)
    cod_spec = svc._build_spec(_BP(), {"blueprint_data": bp_data}, "coding", bp_data["rounds"][1], 10)
    assert apt_spec["topics"] == ["Verbal Ability"]
    assert set(cod_spec["topics"]) == {"SQL & Querying", "Software Engineering & Design Patterns"}
    assert not (set(cod_spec["topics"]) & set(apt_spec["topics"]))
