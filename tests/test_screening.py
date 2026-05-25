"""
Tests for the Stage 3 Screening Service.

Uses the existing database setup — no separate test database needed.
Run:  python -m pytest tests/test_screening.py -v
"""
import json
import sys
import os
import uuid

import pytest
from shared.db.database import get_db
from shared.db.models import Candidate, Job


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db_session():
    """Get a database session for testing."""
    db_gen = get_db()
    session = next(db_gen)
    yield session
    try:
        next(db_gen)
    except StopIteration:
        pass


@pytest.fixture
def sample_job(db_session):
    """Insert a sample job and return it."""
    job = Job(
        title="Python Developer",
        skills=json.dumps(["python", "sql", "fastapi", "docker"]),
        experience_min=3,
        experience_max=5,
        qualification="bachelor's",
        location="Pune",
    )
    db_session.add(job)
    db_session.commit()
    return job


def _make_candidate(job_id, **overrides):
    """Helper to build a Candidate with sane defaults."""
    defaults = {
        "name": "Test Candidate",
        "email": "test@example.com",
        "phone": "1234567890",
        "skills": json.dumps(["python", "sql"]),
        "experience_years": 4.0,
        "education": "bachelor's",
        "location": "Pune",
        "source": "resume",
        "job_id": job_id,
    }
    defaults.update(overrides)
    return Candidate(**defaults)


# ── Duplicate Detector Tests ─────────────────────────────────────────────────

class TestDuplicateDetector:

    def test_no_duplicate(self, db_session, sample_job):
        from screening.duplicate_detector import check_duplicate

        c = _make_candidate(sample_job.id, email="unique@example.com")
        db_session.add(c)
        db_session.commit()

        is_dup, original = check_duplicate(c, db_session)
        assert is_dup is False
        assert original is None

    def test_duplicate_by_email(self, db_session, sample_job):
        from screening.duplicate_detector import check_duplicate

        c1 = _make_candidate(sample_job.id, email="alice@example.com", name="Alice A")
        c2 = _make_candidate(sample_job.id, email="alice@example.com", name="Bob B")
        db_session.add_all([c1, c2])
        db_session.commit()

        is_dup, original = check_duplicate(c2, db_session)
        assert is_dup is True
        assert original == c1.id

    def test_duplicate_by_phone(self, db_session, sample_job):
        from screening.duplicate_detector import check_duplicate

        c1 = _make_candidate(sample_job.id, email="a@a.com", phone="9876543210", name="One")
        c2 = _make_candidate(sample_job.id, email="b@b.com", phone="9876543210", name="Two")
        db_session.add_all([c1, c2])
        db_session.commit()

        is_dup, original = check_duplicate(c2, db_session)
        assert is_dup is True
        assert original == c1.id

    def test_duplicate_by_fuzzy_name(self, db_session, sample_job):
        from screening.duplicate_detector import check_duplicate

        c1 = _make_candidate(sample_job.id, email="a@a.com", phone="111", name="Alice Johnson")
        c2 = _make_candidate(sample_job.id, email="b@b.com", phone="222", name="Alice Jhonson")  # typo
        db_session.add_all([c1, c2])
        db_session.commit()

        is_dup, original = check_duplicate(c2, db_session)
        assert is_dup is True
        assert original == c1.id


# ── Scoring Engine Tests ─────────────────────────────────────────────────────

class TestScoringEngine:

    def test_perfect_match(self, db_session, sample_job):
        from screening.scoring_engine import calculate_score

        c = _make_candidate(
            sample_job.id,
            skills=json.dumps(["python", "sql", "fastapi", "docker"]),
            experience_years=5.0,
            education="bachelor's",
            location="Pune",
        )
        db_session.add(c)
        db_session.commit()

        total, breakdown = calculate_score(c, sample_job)
        assert total == 100
        assert breakdown["skill_match"] == 40
        assert breakdown["experience"] == 30
        assert breakdown["education"] == 20
        assert breakdown["location"] == 10

    def test_partial_skills(self, db_session, sample_job):
        from screening.scoring_engine import calculate_score

        c = _make_candidate(
            sample_job.id,
            skills=json.dumps(["python"]),  # 1 of 4
            experience_years=5.0,
            education="bachelor's",
            location="Pune",
        )
        db_session.add(c)
        db_session.commit()

        total, breakdown = calculate_score(c, sample_job)
        assert breakdown["skill_match"] == 10  # 1/4 * 40

    def test_no_experience(self, db_session, sample_job):
        from screening.scoring_engine import calculate_score

        c = _make_candidate(sample_job.id, experience_years=0.0)
        db_session.add(c)
        db_session.commit()

        total, breakdown = calculate_score(c, sample_job)
        assert breakdown["experience"] == 0

    def test_location_mismatch(self, db_session, sample_job):
        from screening.scoring_engine import calculate_score

        c = _make_candidate(sample_job.id, location="Delhi")
        db_session.add(c)
        db_session.commit()

        total, breakdown = calculate_score(c, sample_job)
        assert breakdown["location"] == 0


# ── Processor Tests ──────────────────────────────────────────────────────────

class TestProcessor:

    def test_shortlisted(self, db_session, sample_job):
        from screening.processor import process_candidate

        c = _make_candidate(
            sample_job.id,
            skills=json.dumps(["python", "sql", "fastapi", "docker"]),
            experience_years=5.0,
            education="bachelor's",
            location="Pune",
        )
        db_session.add(c)
        db_session.commit()

        result = process_candidate(c.id, db_session)
        assert result["status"] == "shortlisted"
        assert result["score"] == 100

        # Verify DB was updated
        db_session.refresh(c)
        assert c.status == "shortlisted"
        assert c.score == 100

    def test_rejected_low_score(self, db_session, sample_job):
        from screening.processor import process_candidate

        c = _make_candidate(
            sample_job.id,
            skills=json.dumps(["java"]),
            experience_years=0.0,
            education="high school",
            location="Delhi",
        )
        db_session.add(c)
        db_session.commit()

        result = process_candidate(c.id, db_session)
        assert result["status"] == "rejected"
        assert result["score"] < 70

    def test_duplicate_skips_scoring(self, db_session, sample_job):
        from screening.processor import process_candidate

        # Insert and process c1 first — it's the original
        c1 = _make_candidate(sample_job.id, email="dup@test.com", name="Original")
        db_session.add(c1)
        db_session.commit()

        result1 = process_candidate(c1.id, db_session)
        assert result1["is_duplicate"] is False

        # Now insert c2 with same email — should be detected as duplicate
        c2 = _make_candidate(sample_job.id, email="dup@test.com", name="Clone")
        db_session.add(c2)
        db_session.commit()

        result2 = process_candidate(c2.id, db_session)
        assert result2["is_duplicate"] is True
        assert result2["status"] == "rejected"

        db_session.refresh(c2)
        assert c2.is_duplicate is True
        assert c2.merged_into == c1.id

    def test_missing_candidate(self, db_session):
        from screening.processor import process_candidate

        result = process_candidate("nonexistent-id", db_session)
        assert result is None

    def test_missing_job(self, db_session, sample_job):
        from screening.processor import process_candidate

        c = _make_candidate(
            sample_job.id,
            email="test@nojob.com",
            name="No Job",
        )
        c.job_id = "nonexistent-job-id"
        db_session.add(c)
        db_session.commit()

        result = process_candidate(c.id, db_session)
        assert result["status"] == "rejected"
