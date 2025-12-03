from sqlmodel import create_engine, Session

from .config import settings
from ..models.base import SQLModel  # Import to access all models

# PostgreSQL engine (connection tested and working)
engine = create_engine(settings.DATABASE_URL, echo=False)

# Session manager for dependency injection
def get_session():
    # Return a session (close manually)
    return Session(engine)

# Create all tables (call once after models defined)
def create_db_and_tables():
    SQLModel.metadata.create_all(engine, checkfirst=True)
