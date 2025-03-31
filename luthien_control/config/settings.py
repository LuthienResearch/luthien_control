import os

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings loaded from environment variables."""

    BACKEND_URL: HttpUrl
    OPENAI_API_KEY: SecretStr | None = None

    # Policy configuration
    POLICY_MODULE: str = Field(
        default="luthien_control.policies.examples.no_op.NoOpPolicy",
        description="Python path to the policy class to load (e.g., 'luthien_control.policies.examples.my_policy.MyPolicy')"
    )

    # Database settings (Optional - required only for DB operations)
    POSTGRES_USER: str | None = Field(default=None)
    POSTGRES_PASSWORD: SecretStr | None = Field(default=None)
    POSTGRES_HOST: str | None = Field(default=None)
    POSTGRES_PORT: int | None = Field(default=None)
    POSTGRES_DB: str | None = Field(default=None)  # Default/initial database name

    model_config = SettingsConfigDict(
        # Restore default env_file loading
        env_file=".env", 
        env_file_encoding="utf-8",
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
        # Ensure password is treated as secret
        password = self.POSTGRES_PASSWORD.get_secret_value() if self.POSTGRES_PASSWORD else None
        if not password:
             raise ValueError("Missing POSTGRES_PASSWORD for admin_dsn")
        return f"postgresql://{self.POSTGRES_USER}:{password}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/postgres"


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
        # Ensure password is treated as secret
        password = self.POSTGRES_PASSWORD.get_secret_value() if self.POSTGRES_PASSWORD else None
        if not password:
             raise ValueError("Missing POSTGRES_PASSWORD for base_dsn")
        return f"postgresql://{self.POSTGRES_USER}:{password}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}"


    def get_db_dsn(self, db_name: str | None = None) -> str:
        """Returns the DSN for a specific database name, or the default POSTGRES_DB.
        Raises ValueError if required DB settings or the target db_name are missing.
        """
        target_db = db_name or self.POSTGRES_DB
        if not target_db:
            raise ValueError(
                "Missing target database name (either provide db_name or set POSTGRES_DB)"
            )
        # Base DSN checks user/pass/host/port are present
        base = self.base_dsn # Call property to ensure checks run
        return f"{base}/{target_db}"