"""
Alembic migration environment.

Imports the application ``Base`` and all model modules so that
``--autogenerate`` can detect schema changes.
"""

import sys
import os

# Add project root to sys.path so `from app.xxx` imports work
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config.settings import settings
from app.database.base import Base

# Import every model module so that Base.metadata is fully populated.
import app.models.user  # noqa: F401
import app.models.assessment  # noqa: F401
import app.models.aptitude  # noqa: F401
import app.models.proctoring  # noqa: F401
import app.models.interview  # noqa: F401

# ── Alembic Config ────────────────────────────────────────────────────
config = context.config

# Override sqlalchemy.url with the value from our Settings.
# Use .get_section(config.config_ini_section).get to avoid ConfigParser interpolation issues
try:
    config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
except ValueError:
    # If there are special chars like % in password, skip set_main_option
    # and handle directly in run_migrations_online
    pass

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Generates SQL scripts without requiring a live database connection.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    Creates an engine and associates a connection with the context.
    """
    # Use settings.DATABASE_URL directly to avoid ConfigParser interpolation
    from sqlalchemy import create_engine
    
    connectable = create_engine(settings.DATABASE_URL, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
