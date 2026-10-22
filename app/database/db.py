"""Database engine and session configuration.

This module is the single source of truth for database connectivity. It
resolves the connection URL, and — when running under the test harness
(``EDI5_TESTING=1``, set by ``tests/conftest.py``) — it binds to an isolated
PostgreSQL test database instead of the development database.

Safety guarantees:
- Outside the test harness the behaviour is unchanged: the engine/session are
  built from ``settings.DATABASE_URL`` exactly as before.
- Under the test harness, tests may **never** connect to the development
  database. Pointing ``TEST_DATABASE_URL`` at the development database is
  rejected. If no test database is configured, database access fails fast with
  an actionable error rather than silently falling back to development.
"""

import os
from urllib.parse import urlparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings


def database_name(url: str) -> str:
    """Return the database name component of a SQLAlchemy URL ('' if any)."""
    try:
        return (urlparse(url).path or "").lstrip("/").split("?")[0]
    except Exception:
        return ""


# The development database name is derived from the configured application URL.
# Tests are refused if they attempt to bind to this database.
KNOWN_DEV_DATABASE_NAME = database_name(settings.DATABASE_URL)

_UNCONFIGURED_TEST_DB_MESSAGE = (
    "EDI5 database-writing tests require an isolated PostgreSQL test database. "
    "Set the TEST_DATABASE_URL environment variable to a dedicated database "
    "(for example postgresql+psycopg2://USER:PASSWORD@localhost:5432/"
    "ai_placement_platform_test). Tests must not run against the development "
    "database. See docs/DATABASE_WORKFLOW.md."
)


def assert_isolated_test_database(url: str) -> None:
    """Fail fast if ``url`` is not a usable, isolated test database.

    Raises RuntimeError when the URL has no database name or points at the
    known development database.
    """
    name = database_name(url)
    if not name:
        raise RuntimeError(
            "TEST_DATABASE_URL has no database name; refusing to run tests. "
            "See docs/DATABASE_WORKFLOW.md."
        )
    if name == KNOWN_DEV_DATABASE_NAME:
        raise RuntimeError(
            f"Refusing to run tests against the development database "
            f"'{name}'. Configure TEST_DATABASE_URL with a separate test "
            f"database (e.g. '{name}_test'). See docs/DATABASE_WORKFLOW.md."
        )


def _build_engine(url: str):
    """Create a connection-pooled engine appropriate for the URL dialect."""
    if url.startswith("sqlite"):
        return create_engine(url)
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


def _session_factory(bind):
    return sessionmaker(autocommit=False, autoflush=False, bind=bind)


_TESTING = os.environ.get("EDI5_TESTING") == "1"
_TEST_DATABASE_URL = os.environ.get("EDI5_TEST_DATABASE_URL") or os.environ.get(
    "TEST_DATABASE_URL"
)

if not _TESTING:
    # Normal application runtime — unchanged behaviour.
    engine = _build_engine(settings.DATABASE_URL)
    SessionLocal = _session_factory(engine)
elif _TEST_DATABASE_URL:
    # Test harness with an explicitly configured test database.
    assert_isolated_test_database(_TEST_DATABASE_URL)
    engine = _build_engine(_TEST_DATABASE_URL)
    SessionLocal = _session_factory(engine)
else:
    # Test harness with **no** test database configured: install a guard that
    # fails fast on any attempt to open a session. This prevents silent
    # fallback to the development database.
    class _UnconfiguredTestSession:
        """Session factory stand-in that raises before any connection."""

        def __call__(self, *args, **kwargs):  # pragma: no cover - guard path
            raise RuntimeError(_UNCONFIGURED_TEST_DB_MESSAGE)

    engine = _build_engine("sqlite://")
    SessionLocal = _UnconfiguredTestSession()


# ── FastAPI dependency ────────────────────────────────────────────────
def get_db():
    """Yield a database session and ensure it is closed after the request.

    Intended for use with ``Depends(get_db)`` in FastAPI path operations.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
