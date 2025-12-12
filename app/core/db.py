from contextlib import contextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import Session, create_engine

from .config import settings
from ..models.base import SQLModel  # Import to access all models


def _build_async_url(url: str) -> str:
    """Convert sync URL to an async-compatible URL."""
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///")
    if "postgresql+psycopg2" in url:
        return url.replace("postgresql+psycopg2", "postgresql+asyncpg")
    return url


# Single engine instances (avoid recreating per request)
sync_connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
sync_engine = create_engine(settings.DATABASE_URL, echo=False, connect_args=sync_connect_args)

async_engine = create_async_engine(_build_async_url(settings.DATABASE_URL), echo=False)

SessionLocal = sessionmaker(sync_engine, class_=Session, expire_on_commit=False)
AsyncSessionLocal = sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)


@contextmanager
def get_session() -> Session:
    """Yield a database session and always close it."""
    session: Session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


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
    SQLModel.metadata.create_all(sync_engine)
