"""
Tests for Phase 4A: Company Historical Data & Pattern Foundation.

Covers:
 1. TPO can add manual historical drive record with normalized topics.
 2. Admin can add manual historical drive record.
 3. Student / non-TPO is forbidden (403).
 4. TPO can upload JSON historical file with topic normalization.
 5. TPO can upload CSV historical file (rounds, topics, and duration extracted).
 6. TPO can upload DOCX / text historical file with rich multi-skill content.
 7. Equivalence normalization works (DSA -> Data Structures & Algorithms, DP -> Dynamic Programming, OOP -> Object-Oriented Programming).
 8. Multi-source evidence aggregation combines evidence count and computes confidence levels.
 9. TPO can delete a historical source and recalculate the updated pattern.
 10. Generating a pattern with no historical data and fallback=False returns 400.
 11. Generating a pattern with fallback=True utilizes EDI5 benchmark seed data.
 12. TPO can explicitly seed from EDI5 benchmark via /pattern/seed-fallback.
 13. TPO can review and approve a structured pattern.
 14. TPO can list all generated patterns and view EDI5 benchmark catalog.
"""

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
from app.services.edi5_benchmark_seeds import find_edi5_benchmark, select_edi5_benchmark

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
from app.models.company_data import CompanyHistoricalData

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
    email = f"phase4a_{role}_{uid}@test.com"
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
def admin_headers():
    return _register_and_login("admin")


@pytest.fixture(scope="module")
def student_headers():
    return _register_and_login("student")


BASE_HISTORICAL_URL = "/api/v1/tpo/company-data/historical"
BASE_PATTERN_URL = "/api/v1/tpo/company-data/pattern"


# ── 1. Manual Historical Data & Normalization ─────────────────────────

def test_tpo_add_manual_historical_data_with_normalization(tpo_headers):
    payload = {
        "company_name": "Google",
        "target_role": "Software Engineer",
        "label": "2024 Campus Drive",
        "raw_data": {
            "year": 2024,
            "rounds": ["aptitude", "coding", "technical_interview"],
            "topics": ["dsa", "DP", "graphs", "system design", "oops"],
            "difficulty": "hard",
            "question_types": ["MCQ", "Coding"],
            "duration_minutes": 120,
        },
    }
    res = client.post(BASE_HISTORICAL_URL, json=payload, headers=tpo_headers)
    assert res.status_code == 201
    data = res.json()
    assert data["company_name"] == "Google"
    assert data["target_role"] == "Software Engineer"
    assert data["source_type"] == "manual"
    raw_topics = data["raw_data"]["topics"]
    # Check that acronyms were normalized to canonical taxonomy names
    assert "Data Structures & Algorithms" in raw_topics
    assert "Dynamic Programming" in raw_topics
    assert "Object-Oriented Programming" in raw_topics


def test_student_cannot_add_historical_data(student_headers):
    payload = {
        "company_name": "Amazon",
        "target_role": "SDE-1",
        "label": "Drive",
        "raw_data": {},
    }
    res = client.post(BASE_HISTORICAL_URL, json=payload, headers=student_headers)
    assert res.status_code == 403


# ── 2. Rich Document Extractions (JSON, CSV, DOCX) ────────────────────

def test_tpo_upload_json_historical_file(tpo_headers):
    json_content = b'{"year": 2023, "rounds": ["aptitude", "coding"], "topics": ["arrays", "hashmap", "cn", "os"], "difficulty": "medium"}'
    files = {"file": ("google_drive.json", io.BytesIO(json_content), "application/json")}
    data = {
        "company_name": "Google",
        "target_role": "Software Engineer",
        "label": "JSON History",
    }
    res = client.post(f"{BASE_HISTORICAL_URL}/upload", data=data, files=files, headers=tpo_headers)
    assert res.status_code == 201
    res_data = res.json()
    assert res_data["source_type"] == "file_upload"
    assert res_data["file_name"] == "google_drive.json"
    raw = res_data["raw_data"]
    assert "Arrays" in raw["topics"]
    assert "Computer Networks" in raw["topics"]
    assert "Operating Systems" in raw["topics"]


def test_tpo_upload_csv_with_stages_and_topics(tpo_headers):
    csv_content = (
        b"Round,Duration,Questions,Topics,Difficulty\n"
        b"Aptitude,60,30,\"Quantitative, Logical Reasoning, Verbal\",medium\n"
        b"Coding,90,3,\"Arrays, Graphs, DP\",hard\n"
        b"Technical Interview,45,2,\"System Design, DBMS, OOPS\",hard\n"
    )
    files = {"file": ("amazon_stages.csv", io.BytesIO(csv_content), "text/csv")}
    data = {
        "company_name": "Amazon",
        "target_role": "Software Development Engineer",
        "label": "Amazon CSV",
    }
    res = client.post(f"{BASE_HISTORICAL_URL}/upload", data=data, files=files, headers=tpo_headers)
    assert res.status_code == 201
    res_data = res.json()
    raw = res_data["raw_data"]
    assert "aptitude" in raw.get("rounds", [])
    assert "coding" in raw.get("rounds", [])
    assert "technical_interview" in raw.get("rounds", [])
    assert "Dynamic Programming" in raw.get("topics", [])
    assert "Database Management Systems" in raw.get("topics", [])


def test_tpo_upload_docx_with_full_placement_experience(tpo_headers):
    # Construct a realistic docx document with headings and multiple skills
    docx_buf = io.BytesIO()
    with zipfile.ZipFile(docx_buf, "w") as z:
        doc_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:body>'
            '<w:p><w:r><w:t>Amazon Placement Drive Experience 2024</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>Round 1: Online Assessment (60 mins, 20 MCQs and 2 Coding Problems). '
            'Topics: Quantitative Aptitude, Logical Reasoning, Arrays, Trees, Dynamic Programming.</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>Round 2: Technical Interview (45 mins). '
            'Deep dive into Object-Oriented Programming, Operating Systems, and System Design scalability.</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>Round 3: Behavioral HR Round (30 mins). '
            'Questions on Amazon Leadership Principles and past project challenges.</w:t></w:r></w:p>'
            '<w:p><w:r><w:t>Overall difficulty level: hard.</w:t></w:r></w:p>'
            '</w:body></w:document>'
        )
        z.writestr("word/document.xml", doc_xml)

    files = {"file": ("amazon_experience.docx", io.BytesIO(docx_buf.getvalue()), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {
        "company_name": "Amazon",
        "target_role": "Software Development Engineer",
        "label": "Amazon Comprehensive Experience",
    }
    res = client.post(f"{BASE_HISTORICAL_URL}/upload", data=data, files=files, headers=tpo_headers)
    assert res.status_code == 201
    raw = res.json()["raw_data"]
    assert "aptitude" in raw.get("rounds", [])
    assert "coding" in raw.get("rounds", [])
    assert "technical_interview" in raw.get("rounds", [])
    assert "hr_interview" in raw.get("rounds", [])
    assert "Dynamic Programming" in raw.get("topics", [])
    assert "Trees & Binary Search Trees" in raw.get("topics", [])
    assert "Operating Systems" in raw.get("topics", [])
    assert "System Design" in raw.get("topics", [])
    assert raw.get("difficulty") == "hard"


# ── 3. Multi-Source Evidence Aggregation & Confidence ─────────────────

def test_multi_source_evidence_aggregation(tpo_headers):
    # Amazon Software Development Engineer now has 2 sources (1 CSV, 1 DOCX)
    res = client.post(
        f"{BASE_PATTERN_URL}/generate?company_name=Amazon&target_role=Software Development Engineer",
        headers=tpo_headers,
    )
    assert res.status_code == 200
    pattern = res.json()
    assert pattern["source_count"] == 2

    pdata = pattern["pattern_data"]
    assert pdata["evidence_count"] >= 10
    assert pdata["confidence_level"] in ("medium", "high")
    assert pdata["confidence_score"] >= 0.60
    assert len(pdata["sources_summary"]) == 2

    # Check topic frequency structure
    tf_list = pdata["topic_frequency"]
    assert len(tf_list) >= 5
    for tf in tf_list:
        assert "topic" in tf
        assert "sources_count" in tf
        assert "frequency_pct" in tf
        assert "category" in tf


# ── 4. Deletion and Recalculation ─────────────────────────────────────

def test_delete_source_and_recalculate(tpo_headers):
    # Add a temporary 3rd source for Amazon
    create_res = client.post(
        BASE_HISTORICAL_URL,
        json={
            "company_name": "Amazon",
            "target_role": "Software Development Engineer",
            "label": "Temporary Source",
            "raw_data": {"topics": ["Bit Manipulation"], "rounds": ["coding"]},
        },
        headers=tpo_headers,
    )
    src_id = create_res.json()["id"]

    # Recalculate -> source count should be 3
    res_3 = client.post(
        f"{BASE_PATTERN_URL}/generate?company_name=Amazon&target_role=Software Development Engineer",
        headers=tpo_headers,
    )
    assert res_3.json()["source_count"] == 3

    # Delete temporary source
    del_res = client.delete(f"{BASE_HISTORICAL_URL}/{src_id}", headers=tpo_headers)
    assert del_res.status_code == 204

    # Recalculate -> source count should drop back to 2
    res_2 = client.post(
        f"{BASE_PATTERN_URL}/generate?company_name=Amazon&target_role=Software Development Engineer",
        headers=tpo_headers,
    )
    assert res_2.json()["source_count"] == 2


# ── 5. EDI5 Benchmark Seed Fallback ───────────────────────────────────

def test_generate_pattern_without_fallback_fails(tpo_headers):
    res = client.post(
        f"{BASE_PATTERN_URL}/generate?company_name=UnseenCompany&target_role=Specialist&use_fallback=false",
        headers=tpo_headers,
    )
    assert res.status_code == 422


def test_unrelated_role_does_not_select_generic_software_benchmark(tpo_headers):
    selection = select_edi5_benchmark("UnseenCompany", "Data Analyst")
    assert selection["status"] == "no_compatible_evidence_found"
    assert selection["benchmark"] is None
    assert find_edi5_benchmark("UnseenCompany", "Data Analyst") is None

    res = client.post(
        f"{BASE_PATTERN_URL}/generate?company_name=NoDAEvidenceCo&target_role=Data Analyst&use_fallback=false",
        headers=tpo_headers,
    )
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "INSUFFICIENT_ROLE_SPECIFIC_EVIDENCE"


def test_legacy_generic_software_seed_is_excluded_from_data_analyst_pattern(tpo_headers):
    created = client.post(
        BASE_HISTORICAL_URL,
        json={
            "company_name": "LegacyGenericSeedCo",
            "target_role": "Data Analyst",
            "label": "Legacy benchmark source",
            "raw_data": {"topics": ["temporary"]},
        },
        headers=tpo_headers,
    )
    assert created.status_code == 201
    db = TestingSessionLocal()
    try:
        source = db.query(CompanyHistoricalData).filter_by(id=created.json()["id"]).one()
        source.source_type = "pre_seeded"
        source.raw_data = {
            "benchmark_reference": "Generic Benchmark - Software Engineer",
            "topics": ["Data Structures & Algorithms", "System Design"],
            "rounds": ["coding", "technical_interview"],
        }
        db.commit()
    finally:
        db.close()

    generated = client.post(
        f"{BASE_PATTERN_URL}/generate?company_name=LegacyGenericSeedCo&target_role=Data Analyst",
        headers=tpo_headers,
    )
    assert generated.status_code == 422
    assert generated.json()["detail"]["selection_status"] == "no_compatible_evidence_found"
    absent = client.get(
        f"{BASE_PATTERN_URL}/LegacyGenericSeedCo/Data Analyst",
        headers=tpo_headers,
    )
    assert absent.status_code == 404


def test_software_engineer_selects_existing_company_role_benchmark(tpo_headers):
    selection = select_edi5_benchmark("Google", "Software Engineer")
    assert selection["status"] == "role_compatible_evidence_found"
    assert selection["benchmark"]["company_name"] == "Google"
    assert selection["benchmark"]["target_role"] == "Software Engineer"


def test_generate_pattern_with_edi5_fallback(tpo_headers):
    res = client.post(
        f"{BASE_PATTERN_URL}/generate?company_name=Microsoft&target_role=Software Engineer&use_fallback=true",
        headers=tpo_headers,
    )
    assert res.status_code == 200
    pattern = res.json()
    assert pattern["company_name"] == "Microsoft"
    pdata = pattern["pattern_data"]
    assert pdata["is_fallback"] is True
    assert pdata["source_provenance"]["classification"] == "pre_seeded_benchmark"
    assert pdata["source_provenance"]["explicit_fallback_requested"] is True
    assert "EDI5 benchmark" in pdata["confidence_level"]
    assert "Data Structures & Algorithms" in pdata["topics"]


def test_explicit_data_analyst_fallback_is_marked_generic(tpo_headers):
    res = client.post(
        f"{BASE_PATTERN_URL}/generate?company_name=ExplicitFallbackCo&target_role=Data Analyst&use_fallback=true",
        headers=tpo_headers,
    )
    assert res.status_code == 200
    provenance = res.json()["pattern_data"]["source_provenance"]
    assert provenance["classification"] == "generic_fallback"
    assert provenance["explicit_fallback_requested"] is True
    assert provenance["empirical_source_count"] == 0


def test_explicit_seed_fallback_endpoint(tpo_headers):
    res = client.post(
        f"{BASE_PATTERN_URL}/seed-fallback",
        json={"company_name": "TCS", "target_role": "Digital / Prime"},
        headers=tpo_headers,
    )
    assert res.status_code == 201
    seeded = res.json()
    assert seeded["source_type"] == "pre_seeded"
    assert "TCS" in seeded["company_name"]


def test_list_edi5_benchmarks(tpo_headers):
    res = client.get("/api/v1/tpo/company-data/benchmarks", headers=tpo_headers)
    assert res.status_code == 200
    benchmarks = res.json()
    assert len(benchmarks) >= 4
    names = [b["company_name"] for b in benchmarks]
    assert "Google" in names
    assert "Amazon" in names


# ── 6. TPO Review & Approval ──────────────────────────────────────────

def test_tpo_review_and_approve_pattern(tpo_headers):
    # Review Amazon pattern
    res = client.post(
        f"{BASE_PATTERN_URL}/Amazon/Software Development Engineer/review",
        json={"status": "approved", "notes": "Verified alignment with 2024 hiring format."},
        headers=tpo_headers,
    )
    assert res.status_code == 200
    pdata = res.json()["pattern_data"]
    assert pdata["review_status"] == "approved"
    assert "Reviewed by" not in pdata or pdata["reviewed_by"] is not None
    assert pdata["review_notes"] == "Verified alignment with 2024 hiring format."


# ── 7. Regression Tests: Non-Skill Filtering & Technical Topic Preservation ──

def test_topic_normalization_filters_non_skill_phrases():
    from app.services.topic_taxonomy import normalize_topic, extract_topics_from_text

    # Problematic non-skill phrases that MUST be rejected (empty string)
    invalid_phrases = [
        "Expected Outcome",
        "Expected Outcomes",
        "We Are Looking For",
        "Preferred",
        "Good To Have",
        "Nice To Have",
        "Mentorship From Experienced Professionals",
        "Job Description",
        "Eligibility Criteria",
        "Requirements",
        "What You Will Do",
        "Perks & Benefits",
        "Candidate Profile",
        "Responsibilities",
    ]
    for phrase in invalid_phrases:
        assert normalize_topic(phrase) == "", f"Expected '{phrase}' to normalize to empty string, got '{normalize_topic(phrase)}'"

    # Real technical topics that MUST be preserved and normalized
    valid_topics = {
        "Python": "Python",
        "python3": "Python",
        "sql": "SQL & Querying",
        "DBMS": "Database Management Systems",
        "System Design": "System Design",
        "data warehousing": "Data Warehousing",
        "Snowflake": "Data Warehousing",
        "MLOps": "MLOps",
        "mlflow": "MLOps",
        "big data": "Big Data",
        "PySpark": "Big Data",
        "dsa": "Data Structures & Algorithms",
        "DP": "Dynamic Programming",
        "Docker": "Cloud Computing & DevOps",
        "Kubernetes": "Cloud Computing & DevOps",
    }
    for raw, expected in valid_topics.items():
        assert normalize_topic(raw) == expected, f"Expected '{raw}' -> '{expected}', got '{normalize_topic(raw)}'"

    # Text extraction scanning: only real skills extracted from noisy document snippet
    noisy_text = (
        "Job Description: We Are Looking For proactive engineers.\n"
        "Requirements: Preferred candidate with good communication.\n"
        "Good To Have: Mentorship From Experienced Professionals and leadership abilities.\n"
        "Technical Skills: Python, SQL, DBMS, System Design, Data Warehousing, MLOps, Big Data.\n"
        "Expected Outcome: High performance and scalable solutions."
    )
    extracted = extract_topics_from_text(noisy_text)
    extracted_canonical = [t[0] for t in extracted]

    # Non-skills must NOT be present
    for bad in ["Expected Outcome", "We Are Looking For", "Preferred", "Good To Have", "Mentorship From Experienced Professionals"]:
        assert bad not in extracted_canonical

    # Real technical topics must be present
    assert "Python" in extracted_canonical
    assert "SQL & Querying" in extracted_canonical
    assert "Database Management Systems" in extracted_canonical
    assert "System Design" in extracted_canonical
    assert "Data Warehousing" in extracted_canonical
    assert "MLOps" in extracted_canonical
    assert "Big Data" in extracted_canonical


def test_document_extraction_ignores_hr_boilerplate(tpo_headers):
    # Upload JSON containing mixture of real technical topics and non-skill phrases
    payload = {
        "company_name": "DataCorp",
        "target_role": "Data Engineer",
        "label": "2024 Data Engineer JD",
        "raw_data": {
            "year": 2024,
            "rounds": ["technical_interview", "coding"],
            "topics": [
                "Expected Outcome",
                "We Are Looking For",
                "Python",
                "SQL",
                "DBMS",
                "Data Warehousing",
                "MLOps",
                "Big Data",
                "Preferred",
                "Good To Have",
                "Mentorship From Experienced Professionals",
            ],
            "difficulty": "hard",
        },
    }
    res = client.post(BASE_HISTORICAL_URL, json=payload, headers=tpo_headers)
    assert res.status_code == 201
    raw = res.json()["raw_data"]

    # In raw_data["topics"], invalid phrases should have been omitted
    assert "Expected Outcome" not in raw["topics"]
    assert "We Are Looking For" not in raw["topics"]
    assert "Preferred" not in raw["topics"]
    assert "Good To Have" not in raw["topics"]
    assert "Mentorship From Experienced Professionals" not in raw["topics"]

    # Valid topics must exist
    assert "Python" in raw["topics"]
    assert "SQL & Querying" in raw["topics"]
    assert "Database Management Systems" in raw["topics"]
    assert "Data Warehousing" in raw["topics"]
    assert "MLOps" in raw["topics"]
    assert "Big Data" in raw["topics"]

    # Generate pattern and check topic frequency
    pat_res = client.post(
        f"{BASE_PATTERN_URL}/generate?company_name=DataCorp&target_role=Data Engineer",
        headers=tpo_headers,
    )
    assert pat_res.status_code == 200
    pattern_data = pat_res.json()["pattern_data"]
    tf_topics = [item["topic"] for item in pattern_data["topic_frequency"]]

    assert "Expected Outcome" not in tf_topics
    assert "We Are Looking For" not in tf_topics
    assert "Preferred" not in tf_topics
    assert "Mentorship From Experienced Professionals" not in tf_topics

    assert "Python" in tf_topics
    assert "SQL & Querying" in tf_topics
    assert "Data Warehousing" in tf_topics
    assert "MLOps" in tf_topics
    assert "Big Data" in tf_topics
