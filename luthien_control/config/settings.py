from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import HttpUrl


class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables."""
    BACKEND_URL: HttpUrl

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

# Load settings instance
settings = Settings()
