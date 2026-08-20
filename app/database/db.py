"""
Database engine, session factory, and FastAPI dependency.

Usage in routers / services::

    from app.database.db import get_db

    @router.get("/items")
    def list_items(db: Session = Depends(get_db)):
        ...
"""

from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import settings

# ── Engine & session factory ──────────────────────────────────────────
# Pool parameters are environment-driven (DB_POOL_*) with conservative defaults
# suitable for a single-instance deployment. Scale up via env when running
# multiple FastAPI instances behind a load balancer.

# Stage 2 hardening: optional libpq sslmode passed through connect_args.
connect_args: dict = {}
if settings.DB_SSL_MODE:
    connect_args["sslmode"] = settings.DB_SSL_MODE

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_recycle=settings.DB_POOL_RECYCLE,
    connect_args=connect_args,
)

# Stage 2 hardening: optional per-statement timeout. Applied on every
# connection checkout so a runaway query cannot hold a pooled connection.
if settings.DB_STATEMENT_TIMEOUT_MS > 0:
    _timeout_ms = int(settings.DB_STATEMENT_TIMEOUT_MS)

    @event.listens_for(engine, "checkout")
    def _set_statement_timeout(dbapi_conn, conn_record, conn_proxy):  # type: ignore[var-annotated]
        try:
            # Use SET LOCAL so the timeout only applies to the current transaction
            # being opened on this checkout (resets when the transaction ends).
            with dbapi_conn.cursor() as cur:
                cur.execute(
                    "SET LOCAL statement_timeout = %s", (_timeout_ms,)
                )
        except Exception:
            # Don't break request handling if the timeout can't be applied
            # (e.g. non-superuser connection that lacks SET privileges).
            pass

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


# ── FastAPI dependency ────────────────────────────────────────────────
def get_db() -> Generator[Session, None, None]:
    """Yield a database session and ensure it is closed after the request.

    Intended for use with ``Depends(get_db)`` in FastAPI path operations.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
