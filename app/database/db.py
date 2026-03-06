"""
Database engine, session factory, and FastAPI dependency.

Usage in routers / services::

    from app.database.db import get_db

    @router.get("/items")
    def list_items(db: Session = Depends(get_db)):
        ...
"""

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import settings

# ── Engine & session factory ──────────────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

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
