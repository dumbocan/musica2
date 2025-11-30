from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Load env from .env file
    model_config = {"env_file": ".env"}

    DATABASE_URL: str

# Instantiate settings
settings = Settings()
