import os
import sys
from pathlib import Path
from urllib.parse import urlparse

# Ensure repository root is on PYTHONPATH for imports like `app.*`
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Signal to app.database.db that we are running tests. This MUST happen before
# any application module (and therefore app.database.db) is imported, so that
# database connectivity is bound to the isolated test database (or guarded)
# rather than the development database. See docs/DATABASE_WORKFLOW.md.
# Force (not setdefault): the isolation guard must never be defeatable by a
# pre-existing EDI5_TESTING=0 in the shell environment.
os.environ["EDI5_TESTING"] = "1"

# Workaround: make PostgreSQL JSONB available as SQLAlchemy JSON for SQLite tests
try:
    from sqlalchemy import JSON
    import sqlalchemy.dialects.postgresql as _pg

    _pg.JSONB = JSON
except Exception:
    pass

# Enable pytest-asyncio
pytest_plugins = ["pytest_asyncio"]


def _test_database_url() -> str | None:
    return os.environ.get("EDI5_TEST_DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")


def _admin_url(test_url: str) -> str:
    """Return a connection URL pointing at the maintenance 'postgres' DB."""
    parsed = urlparse(test_url)
    return parsed._replace(path="/postgres").geturl()


def _import_all_models() -> None:
    import app.models  # noqa: F401
    import app.models.company_data  # noqa: F401
    import app.models.mock_drive  # noqa: F401
    import app.models.question_pool_generation  # noqa: F401
    import app.models.assessment_context  # noqa: F401


def _provision_isolated_test_database(test_url: str) -> None:
    """Drop + recreate the isolated test database and build its schema.

    Only ever operates on the configured test database; the development
    database is never touched.
    """
    from sqlalchemy import create_engine
    from app.database.db import assert_isolated_test_database, database_name, engine
    from app.database.base import Base

    assert_isolated_test_database(test_url)
    name = database_name(test_url)

    admin_engine = create_engine(_admin_url(test_url), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
            conn.execute(text(f'CREATE DATABASE "{name}"'))
    finally:
        admin_engine.dispose()

    _import_all_models()
    Base.metadata.create_all(bind=engine)
    _seed_baseline(engine)


def _teardown_isolated_test_database(test_url: str) -> None:
    """Drop the isolated test database. Never touches the development DB."""
    from sqlalchemy import create_engine, text
    from app.database.db import assert_isolated_test_database, database_name, engine

    assert_isolated_test_database(test_url)
    name = database_name(test_url)

    engine.dispose()
    admin_engine = create_engine(_admin_url(test_url), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        admin_engine.dispose()


def _seed_baseline(engine) -> None:
    """Insert the deterministic baseline rows the suite relies on.

    Mirrors the data seeded by the assessment-context migration so tests do not
    depend on rows already present in the development database.
    """
    from sqlalchemy import text

    with engine.begin() as conn:
        conn.execute(text(
            """
            INSERT INTO assessment_policies
                (id, name, session_duration_minutes, round_duration_minutes,
                 max_attempts, resume_allowed, exit_allowed, progression_mode,
                 progression_config)
            VALUES
                (1, 'Legacy Practice Policy', 180, 30, NULL, true, true,
                 'sequential',
                 '{"rounds": ["aptitude", "coding", "interview"]}'::jsonb),
                (2, 'Practice Policy', 180, 30, NULL, true, true,
                 'independent', '{}'::jsonb)
            ON CONFLICT (id) DO NOTHING
            """
        ))
        conn.execute(text(
            """
            INSERT INTO assessment_contexts (id, mode, purpose, policy_id, status)
            VALUES (1, 'practice', 'legacy', 1, 'active')
            ON CONFLICT (id) DO NOTHING
            """
        ))
        conn.execute(text(
            "SELECT setval(pg_get_serial_sequence('assessment_policies','id'),"
            " (SELECT COALESCE(MAX(id), 1) FROM assessment_policies))"
        ))
        conn.execute(text(
            "SELECT setval(pg_get_serial_sequence('assessment_contexts','id'),"
            " (SELECT COALESCE(MAX(id), 1) FROM assessment_contexts))"
        ))


import pytest  # noqa: E402


def _reset_rate_limiter() -> None:
    """Clear the in-process HTTP rate-limiter state, if the app is imported.

    ``RateLimitMiddleware`` keeps a per-client-IP token bucket on the shared
    ``app`` instance. Because every ``TestClient`` reuses that same instance,
    request counts leak across modules and an unrelated test can collect a
    spurious HTTP 429. Resetting between tests keeps rate-limit behaviour
    deterministic without weakening production limits.

    This is a no-op for service-level suites that never import ``app.main``
    (e.g. pure-SQLite tests), so it cannot add import-time dependencies.
    """
    main_module = sys.modules.get("app.main")
    app = getattr(main_module, "app", None) if main_module is not None else None
    if app is None:
        return
    from app.middleware.rate_limit import RateLimitMiddleware

    stack = app.middleware_stack or app.build_middleware_stack()
    app.middleware_stack = stack
    current = stack
    while current is not None and not isinstance(current, RateLimitMiddleware):
        current = getattr(current, "app", None)
    if current is not None:
        current._requests.clear()


@pytest.fixture(autouse=True)
def _isolate_rate_limiter():
    """Reset the shared rate-limiter around every test."""
    _reset_rate_limiter()
    yield
    _reset_rate_limiter()


@pytest.fixture(scope="session", autouse=True)
def edi5_isolated_test_database():
    """Provision the isolated test database once per test session.

    If no test database is configured, this fixture does nothing and database
    access fails fast via the guard in ``app.database.db``.
    """
    os.environ["EDI5_TESTING"] = "1"
    test_url = _test_database_url()
    if test_url:
        _provision_isolated_test_database(test_url)
    yield
    if test_url:
        _teardown_isolated_test_database(test_url)
