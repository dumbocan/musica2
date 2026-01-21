from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings
from typing import Optional


DEFAULT_DEV_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:5175",
    "http://localhost:5176",
    "http://localhost:5177",
    "http://localhost:5178",
    "http://localhost:5179",
    "http://localhost:5180",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:5174",
    "http://127.0.0.1:5175",
    "http://127.0.0.1:5176",
    "http://127.0.0.1:5177",
    "http://127.0.0.1:5178",
    "http://127.0.0.1:5179",
    "http://127.0.0.1:5180",
]


class Settings(BaseSettings):
    """
    Centralized configuration with safe defaults so the app can start
    even if the user has not populated every API key yet.
    """

    model_config = {"env_file": ".env"}

    # Database: PostgreSQL only (required)
    DATABASE_URL: str = ""

    # APIs (optional for boot, required when those features are used)
    SPOTIFY_CLIENT_ID: Optional[str] = None
    SPOTIFY_CLIENT_SECRET: Optional[str] = None
    LASTFM_API_KEY: Optional[str] = None
    MUSIXMATCH_API_KEY: Optional[str] = None
    YOUTUBE_API_KEY: Optional[str] = None
    YOUTUBE_API_KEY_2: Optional[str] = None

    # Chart scraping (Billboard)
    CHART_BACKFILL_START_DATE: Optional[str] = "1960-01-01"
    CHART_BACKFILL_YEARS: int = 5
    CHART_MAX_WEEKS_PER_RUN: int = 20
    CHART_REFRESH_INTERVAL_HOURS: int = 24
    CHART_MATCH_REFRESH_INTERVAL_HOURS: int = 12
    CHART_MAX_RANK: int = 5
    CHART_REQUEST_MIN_DELAY_SECONDS: float = 0.8
    CHART_REQUEST_MAX_DELAY_SECONDS: float = 1.8

    # Maintenance scheduling
    MAINTENANCE_ENABLED: bool = True
    MAINTENANCE_START_ON_FIRST_REQUEST: bool = False
    MAINTENANCE_STARTUP_DELAY_SECONDS: int = 60
    MAINTENANCE_STAGGER_SECONDS: int = 10
    MAINTENANCE_FAVORITES_CONCURRENCY: int = 3
    MAINTENANCE_BACKFILL_DELAY_SECONDS: float = 0.4
    MAINTENANCE_LIBRARY_BATCH_SIZE: int = 120
    MAINTENANCE_LIBRARY_LOOP_SECONDS: int = 2 * 60 * 60
    MAINTENANCE_LIBRARY_DELAY_SECONDS: float = 0.2
    MAINTENANCE_LIBRARY_TOTAL_TIMEOUT_SECONDS: float = 3.0

    # Security
    ENVIRONMENT: str = "development"
    JWT_SECRET_KEY: str = "changeme-in-.env"
    AUTH_RECOVERY_CODE: Optional[str] = None
    CORS_ORIGINS: list[str] = []
    CORS_ALLOW_CREDENTIALS: bool = True

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value:
            raise ValueError("DATABASE_URL is required and must point to PostgreSQL.")
        if not value.startswith("postgresql"):
            raise ValueError("DATABASE_URL must be a PostgreSQL URL (postgresql+psycopg2://...).")
        return value

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value or []

    @model_validator(mode="after")
    def validate_security(self):
        if self.ENVIRONMENT == "production":
            if not self.CORS_ORIGINS:
                raise ValueError("CORS_ORIGINS must be set for production.")
            if not self.JWT_SECRET_KEY or self.JWT_SECRET_KEY == "changeme-in-.env":
                raise ValueError("JWT_SECRET_KEY must be set for production.")
        if self.ENVIRONMENT != "production" and not self.CORS_ORIGINS:
            self.CORS_ORIGINS = DEFAULT_DEV_CORS_ORIGINS
        return self


# Instantiate settings once
settings = Settings()
