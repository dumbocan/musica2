from sqlmodel import create_engine

from .config import settings

# PostgreSQL engine (connection prepared, not active yet)
engine = create_engine(settings.DATABASE_URL, echo=False)

# Future: def get_session(), def create_db(), etc.
