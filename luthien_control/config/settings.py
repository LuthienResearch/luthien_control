import os # Add os import
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import HttpUrl

# Determine the environment file based on APP_ENV
APP_ENV = os.getenv("APP_ENV", "development")
env_file = ".env.test" if APP_ENV == "test" else ".env"

class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables."""
    BACKEND_URL: HttpUrl

    # Load from .env first, then .env.test (if it exists)
    model_config = SettingsConfigDict(env_file=('.env', '.env.test'), extra="ignore")

# Load settings instance
settings = Settings()
