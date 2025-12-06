from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Load env from .env file
    model_config = {"env_file": ".env"}

    # Database
    DATABASE_URL: str

    # APIs
    SPOTIFY_CLIENT_ID: str
    SPOTIFY_CLIENT_SECRET: str
    LASTFM_API_KEY: str
    MUSIXMATCH_API_KEY: Optional[str] = None  # Optional
    YOUTUBE_API_KEY: str  # YouTube Data API v3

# Instantiate settings
settings = Settings()
