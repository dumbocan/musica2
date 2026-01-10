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
