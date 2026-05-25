"""
SQLAlchemy async database engine and session management.
Uses SQLite for development, PostgreSQL for production.
"""
import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import DATABASE_URL


engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def generate_id() -> str:
    return str(uuid.uuid4())[:12]


async def get_db() -> AsyncSession:
    """FastAPI dependency — yields a database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Create all tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Database tables created")

from contextlib import asynccontextmanager

@asynccontextmanager
async def db_session():
    """Context manager for database sessions."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

# Sync session for compatibility with existing code
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Create sync engine for sync operations
sync_database_url = DATABASE_URL
if 'sqlite+aiosqlite' in sync_database_url:
    sync_database_url = sync_database_url.replace('sqlite+aiosqlite', 'sqlite')
elif '+asyncpg' in sync_database_url:
    sync_database_url = sync_database_url.replace('+asyncpg', '')

sync_engine = create_engine(sync_database_url, echo=False)
SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

from contextlib import contextmanager

@contextmanager
def db_session():
    """Sync context manager for database sessions."""
    session = SyncSessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()