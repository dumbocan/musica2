from sqlmodel import create_engine, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from typing import AsyncGenerator

from .config import settings
from ..models.base import SQLModel  # Import to access all models

# PostgreSQL engine (connection tested and working)
# Convert to async URL for SQLAlchemy 2.0
async_database_url = settings.DATABASE_URL.replace("postgresql+psycopg2", "postgresql+asyncpg")
engine = create_async_engine(async_database_url, echo=False)

# Session manager for dependency injection (legacy sync)
def get_session():
    # Return a session (close manually)
    sync_engine = create_engine(settings.DATABASE_URL.replace("postgresql+psycopg2", "postgresql+psycopg2"), echo=False)
    return Session(sync_engine)

# Async session for FastAPI dependency injection
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSession(engine) as session:
        yield session

# FastAPI dependency
SessionDep = get_async_session

# Create all tables (call once after models defined)
def create_db_and_tables():
    # Use sync engine for table creation
    sync_engine = create_engine(settings.DATABASE_URL.replace("postgresql+psycopg2", "postgresql+psycopg2"), echo=False)
    # Drop all tables first to ensure schema matches models
    SQLModel.metadata.drop_all(sync_engine)
    # Create all tables with current schema
    SQLModel.metadata.create_all(sync_engine)
