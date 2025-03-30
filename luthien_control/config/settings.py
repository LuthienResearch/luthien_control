import os # Add os import
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import HttpUrl, SecretStr

class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables."""
    BACKEND_URL: HttpUrl
    OPENAI_API_KEY: SecretStr | None = None # Add OpenAI API Key field

    # Load from the determined env_file
    model_config = SettingsConfigDict(
        # Allow loading from different files based on APP_ENV
        env_file=('.env', '.env.test'), 
        extra="ignore"
    )

@lru_cache()
def get_settings() -> Settings:
    """Loads and returns the application settings.
    
    Uses lru_cache to avoid reloading settings repeatedly.
    Determines which .env file to prioritize based on APP_ENV.
    """
    app_env = os.getenv("APP_ENV", "development")
    if app_env == "test":
        # Prioritize .env.test for testing
        return Settings(_env_file='.env.test', _env_file_encoding='utf-8')
    else:
        # Prioritize .env for development/production
        return Settings(_env_file='.env', _env_file_encoding='utf-8')

# Remove the global instance creation
# settings = Settings()
