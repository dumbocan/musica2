from sqlmodel import create_engine, Session

from .config import settings

# PostgreSQL engine (connection tested and working)
engine = create_engine(settings.DATABASE_URL, echo=False)

# Session manager for dependency injection
def get_session():
    with Session(engine) as session:
        yield session

# Future: def init_db(models)
