import os  # Add os import
from functools import lru_cache

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables."""

    BACKEND_URL: HttpUrl
    OPENAI_API_KEY: SecretStr | None = None  # Add OpenAI API Key field

    # Database settings (Optional - required only for DB operations)
    POSTGRES_USER: str | None = Field(default=None)
    POSTGRES_PASSWORD: SecretStr | None = Field(default=None)
    POSTGRES_HOST: str | None = Field(default=None)
    POSTGRES_PORT: int | None = Field(default=None)
    POSTGRES_DB: str | None = Field(default=None)  # Default/initial database name

    # Load from the determined env_file
    model_config = SettingsConfigDict(
        # Allow loading from different files based on APP_ENV
        # Pydantic-settings looks for unprefixed env vars first, then prefixed.
        # Field name `POSTGRES_USER` looks for env var `POSTGRES_USER` by default.
        env_file=(".env", ".env.test"),
        extra="ignore",
    )

    # --- Database DSN Helper Properties ---
    @property
    def admin_dsn(self) -> str:
        """DSN for connecting to the default 'postgres' db for admin tasks.
        Raises ValueError if required DB settings are missing.
        """
        if not all(
            [
                self.POSTGRES_USER,
                self.POSTGRES_PASSWORD,
                self.POSTGRES_HOST,
                self.POSTGRES_PORT,
            ]
        ):
            raise ValueError(
                "Missing required database settings (USER, PASSWORD, HOST, PORT) for admin_dsn"
            )
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD.get_secret_value()}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/postgres"

    @property
    def base_dsn(self) -> str:
        """Base DSN without a specific database name.
        Raises ValueError if required DB settings are missing.
        """
        if not all(
            [
                self.POSTGRES_USER,
                self.POSTGRES_PASSWORD,
                self.POSTGRES_HOST,
                self.POSTGRES_PORT,
            ]
        ):
            raise ValueError(
                "Missing required database settings (USER, PASSWORD, HOST, PORT) for base_dsn"
            )
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD.get_secret_value()}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}"

    def get_db_dsn(self, db_name: str | None = None) -> str:
        """Returns the DSN for a specific database name, or the default POSTGRES_DB.
        Raises ValueError if required DB settings or the target db_name are missing.
        """
        target_db = db_name or self.POSTGRES_DB
        if not target_db:
            raise ValueError(
                "Missing target database name (either provide db_name or set POSTGRES_DB)"
            )
        if not all(
            [
                self.POSTGRES_USER,
                self.POSTGRES_PASSWORD,
                self.POSTGRES_HOST,
                self.POSTGRES_PORT,
            ]
        ):
            raise ValueError(
                "Missing required database settings (USER, PASSWORD, HOST, PORT) for get_db_dsn"
            )
        return f"{self.base_dsn}/{target_db}"


@lru_cache()
def get_settings() -> Settings:
    """Loads and returns the application settings.

    Uses lru_cache to avoid reloading settings repeatedly.
    Determines which .env file to prioritize based on APP_ENV.
    """
    app_env = os.getenv("APP_ENV", "development")
    if app_env == "test":
        # Prioritize .env.test for testing
        return Settings(_env_file=".env.test", _env_file_encoding="utf-8")
    else:
        # Prioritize .env for development/production
        return Settings(_env_file=".env", _env_file_encoding="utf-8")


# Remove the global instance creation
# settings = Settings()
