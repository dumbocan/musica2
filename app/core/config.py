from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """
    Centralized configuration with safe defaults so the app can start
    even if the user has not populated every API key yet.
    """

    model_config = {"env_file": ".env"}

    # Database: default to local SQLite for quick start
    DATABASE_URL: str = "sqlite:///./audio2.db"

    # APIs (optional for boot, required when those features are used)
    SPOTIFY_CLIENT_ID: Optional[str] = None
    SPOTIFY_CLIENT_SECRET: Optional[str] = None
    LASTFM_API_KEY: Optional[str] = None
    MUSIXMATCH_API_KEY: Optional[str] = None
    YOUTUBE_API_KEY: Optional[str] = None
    YOUTUBE_API_KEY_2: Optional[str] = None

    # Security
    JWT_SECRET_KEY: str = "changeme-in-.env"


# Instantiate settings once
settings = Settings()
