#!/usr/bin/env python3
"""
Standalone script to create the complete database schema for AI Placement Platform.

Run directly: python create_schema.py

Requires: DATABASE_URL environment variable or .env file with PostgreSQL connection string.
"""
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

# Import all models to register them with Base.metadata
from app.database.base import Base
from app.models import (
    User,
    AssessmentSession,
    AssessmentRound,
    AptitudeTopic,
    AptitudeQuestion,
    AptitudeAttempt,
    RLSession,
    CodingProblem,
    CodingTestCase,
    CodingSubmission,
    SessionProblem,
    ProctoringEvent,
    AdvancedProctoringEvent,
    InterviewSession,
    ApprovedQuestionPool,
    InterviewTurn,
    ProctoringViolation,
    ResumeProcessingJob,
    AdminQuestionFeedback,
    RLQTable,
    RLAttemptLog,
)
from app.config.settings import settings


def get_database_url() -> str:
    """Get database URL from settings or environment."""
    if settings.DATABASE_URL:
        return settings.DATABASE_URL
    # Fallback to environment
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL not set. Set it in .env or environment variable.\n"
            "Example: postgresql://user:pass@localhost:5432/dbname"
        )
    return url


def create_schema(engine) -> None:
    """Create all tables using SQLAlchemy metadata."""
    print("Creating all tables...")
    Base.metadata.create_all(bind=engine)
    print("✓ All tables created via SQLAlchemy metadata")


def create_materialized_view(engine) -> None:
    """Create the round_analytics materialized view (not covered by ORM)."""
    ddl = """
    CREATE MATERIALIZED VIEW IF NOT EXISTS round_analytics AS
    SELECT
        r.id AS round_id,
        r.round_type,
        COUNT(aa.id) AS total_questions,
        SUM(CASE WHEN aa.is_correct THEN 1 ELSE 0 END) AS correct_answers,
        AVG(aa.response_time) AS avg_response_time,
        NULL::FLOAT AS coding_score
    FROM assessment_rounds r
    LEFT JOIN aptitude_attempts aa ON aa.round_id = r.id
    WHERE r.round_type = 'aptitude'
    GROUP BY r.id, r.round_type

    UNION ALL

    SELECT
        r.id,
        r.round_type,
        COUNT(cs.id),
        NULL,
        NULL,
        AVG(cs.score)
    FROM assessment_rounds r
    LEFT JOIN coding_submissions cs ON cs.round_id = r.id
    WHERE r.round_type = 'coding'
    GROUP BY r.id, r.round_type;
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))
        # Unique index on materialized view
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_round_analytics_round_id "
            "ON round_analytics(round_id)"
        ))
    print("✓ Materialized view 'round_analytics' created")


def create_partial_index(engine) -> None:
    """Create the partial unique index for one active session per user."""
    ddl = """
    CREATE UNIQUE INDEX IF NOT EXISTS one_active_session_per_user
    ON assessment_sessions(user_id)
    WHERE status='in_progress';
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))
    print("✓ Partial unique index 'one_active_session_per_user' created")


def verify_schema(engine) -> None:
    """Verify all expected tables exist."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    views = inspector.get_view_names()

    expected_tables = {
        "users", "refresh_tokens", "user_resumes",
        "assessment_sessions", "assessment_rounds",
        "aptitude_topics", "aptitude_questions", "admin_question_feedback",
        "aptitude_attempts", "rl_sessions",
        "coding_problems", "coding_test_cases", "session_problems", "coding_submissions",
        "proctoring_events", "advanced_proctoring_events",
        "interview_sessions", "approved_question_pools", "interview_turns", "proctoring_violations",
        "resume_processing_jobs", "rl_q_table", "rl_attempt_log",
    }

    missing = expected_tables - set(tables)
    if missing:
        print(f"⚠ Missing tables: {sorted(missing)}")
    else:
        print(f"✓ All {len(expected_tables)} tables present")

    if "round_analytics" in views:
        print("✓ Materialized view 'round_analytics' present")
    else:
        print("⚠ Materialized view 'round_analytics' missing")


def main() -> int:
    try:
        db_url = get_database_url()
        print(f"Connecting to: {db_url.split('@')[-1] if '@' in db_url else db_url}")

        engine = create_engine(db_url, pool_pre_ping=True)

        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✓ Database connection OK")

        # Create everything
        create_schema(engine)
        create_materialized_view(engine)
        create_partial_index(engine)

        # Verify
        verify_schema(engine)

        print("\n✅ Schema creation complete!")
        return 0

    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())