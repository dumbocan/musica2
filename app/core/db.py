from typing import AsyncGenerator
import logging

from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text
from sqlmodel import Session, create_engine

from .config import settings
from ..models.base import SQLModel  # Import to access all models

logger = logging.getLogger(__name__)

def _build_async_url(url: str) -> str:
    """Convert sync URL to an async-compatible URL."""
    if "postgresql+psycopg2" in url:
        return url.replace("postgresql+psycopg2", "postgresql+asyncpg")
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


# Single engine instances (avoid recreating per request)
if not settings.DATABASE_URL.startswith("postgresql"):
    raise RuntimeError("DATABASE_URL must be a PostgreSQL URL. Check your .env.")

sync_engine = create_engine(settings.DATABASE_URL, echo=False)

async_engine = create_async_engine(_build_async_url(settings.DATABASE_URL), echo=False)

SessionLocal = sessionmaker(sync_engine, class_=Session, expire_on_commit=False)
AsyncSessionLocal = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)


def get_session() -> Session:
    """Return a new database session; caller must close()."""
    return SessionLocal()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Async session dependency for FastAPI."""
    async with AsyncSessionLocal() as session:
        yield session


# FastAPI dependency
SessionDep = get_async_session


def create_db_and_tables() -> None:
    """
    Create tables if they do not exist.
    Non-destructive: avoids dropping existing data.
    """
    try:
        with sync_engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    except Exception as exc:
        logger.warning("pg_trgm extension unavailable: %s", exc)
    SQLModel.metadata.create_all(sync_engine)
    try:
        with sync_engine.begin() as conn:
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_playhistory_user_id ON playhistory (user_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_playhistory_user_track ON playhistory (user_id, track_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_playhistory_user_played_at ON playhistory (user_id, played_at DESC)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_userfavorite_user_id ON userfavorite (user_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_userfavorite_user_track ON userfavorite (user_id, track_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_userfavorite_user_artist ON userfavorite (user_id, artist_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_userfavorite_user_target ON userfavorite (user_id, target_type)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_userhiddenartist_user_id ON userhiddenartist (user_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_userhiddenartist_user_artist ON userhiddenartist (user_id, artist_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_artist_popularity ON artist (popularity DESC, id ASC)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_artist_name_order ON artist (name ASC, id ASC)"))
    except Exception as exc:
        logger.warning("Index setup skipped: %s", exc)
