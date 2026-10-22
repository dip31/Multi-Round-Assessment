"""Guard tests: the test harness must never bind to the development database.

These tests do not require a configured test database; they exercise the
database-isolation guard directly.
"""

import pytest

from app.database.db import (
    KNOWN_DEV_DATABASE_NAME,
    assert_isolated_test_database,
    database_name,
)


def test_development_database_is_rejected():
    """Binding tests to the development database must fail fast."""
    dev_url = f"postgresql+psycopg2://user:secret@localhost:5432/{KNOWN_DEV_DATABASE_NAME}"
    with pytest.raises(RuntimeError, match="development database"):
        assert_isolated_test_database(dev_url)


def test_dedicated_test_database_is_allowed():
    """A clearly separate test database is accepted."""
    test_url = (
        f"postgresql+psycopg2://user:secret@localhost:5432/"
        f"{KNOWN_DEV_DATABASE_NAME}_test"
    )
    assert_isolated_test_database(test_url) is None


def test_url_without_database_name_is_rejected():
    """A URL with no database name is not a valid test target."""
    with pytest.raises(RuntimeError, match="no database name"):
        assert_isolated_test_database("postgresql+psycopg2://user:secret@localhost:5432/")


def test_database_name_extraction():
    assert database_name("postgresql+psycopg2://u:p@localhost:5432/my_db") == "my_db"
    assert database_name("postgresql+psycopg2://u:p@localhost:5432/my_db?sslmode=disable") == "my_db"
    assert database_name("") == ""
