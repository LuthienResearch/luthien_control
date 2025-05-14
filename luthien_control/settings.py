import os
from typing import Optional
from urllib.parse import urlparse

from dotenv import load_dotenv

# Load .env file variables into environment
load_dotenv(verbose=True)


class Settings:
    """Application configuration settings loaded from environment variables."""

    # --- Core Settings ---
    BACKEND_URL: Optional[str] = None
    # Comma-separated list of control policies for the beta framework

    # --- Database Settings ---
    DB_SERVER: str = "localhost"
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    DB_NAME: Optional[str] = None
    DB_HOST: Optional[str] = None
    DB_PORT: Optional[int] = 5432

    # --- OpenAI Settings ---
    OPENAI_API_KEY: Optional[str] = None

    # --- Helper Methods using os.getenv ---
    def get_backend_url(self) -> Optional[str]:
        """Returns the backend URL as a string, if set."""
        url = os.getenv("BACKEND_URL")
        if url:
            # Basic validation (can be enhanced)
            parsed = urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                raise ValueError(f"Invalid BACKEND_URL format: {url}")
        return url

    def get_database_url(self) -> Optional[str]:
        """Returns the primary DATABASE_URL, if set."""
        return os.getenv("DATABASE_URL")

    def get_openai_api_key(self) -> str | None:
        """Returns the OpenAI API key, if set."""
        return os.getenv("OPENAI_API_KEY")

    def get_top_level_policy_name(self) -> str:
        """Returns the name of the top-level policy instance to load."""
        return os.getenv("TOP_LEVEL_POLICY_NAME", "root")

    def get_policy_filepath(self) -> str:
        """Returns the path to the policy file, if set."""
        return os.getenv("POLICY_FILEPATH")

    # --- Database settings Getters using os.getenv ---
    def get_postgres_user(self) -> str | None:
        return os.getenv("DB_USER")

    def get_postgres_password(self) -> str | None:
        return os.getenv("DB_PASSWORD")

    def get_postgres_db(self) -> str | None:
        return os.getenv("DB_NAME")

    def get_postgres_host(self) -> str | None:
        return os.getenv("DB_HOST")

    def get_postgres_port(self) -> int | None:
        """Returns the PostgreSQL port as an integer, or None if not set."""
        port_str = os.getenv("DB_PORT")
        if port_str is None:
            return None
        try:
            return int(port_str)
        except ValueError:
            raise ValueError("DB_PORT environment variable must be an integer.")

    # --- DB Pool Size Getters ---
    def get_main_db_pool_min_size(self) -> int:
        """Returns the minimum pool size for the main DB."""
        try:
            return int(os.getenv("MAIN_DB_POOL_MIN_SIZE", "1"))
        except ValueError:
            raise ValueError("MAIN_DB_POOL_MIN_SIZE environment variable must be an integer.")

    def get_main_db_pool_max_size(self) -> int:
        """Returns the maximum pool size for the main DB."""
        try:
            return int(os.getenv("MAIN_DB_POOL_MAX_SIZE", "10"))
        except ValueError:
            raise ValueError("MAIN_DB_POOL_MAX_SIZE environment variable must be an integer.")

    # --- Logging Settings --- # Added based on grep results
    def get_log_level(self, default: str = "INFO") -> str:
        """Gets the configured log level, defaulting if not set."""
        return os.getenv("LOG_LEVEL", default).upper()

    # --- Database DSN Helper Properties using Getters ---
    @property
    def admin_dsn(self) -> str:
        """DSN for connecting to the default 'postgres' db for admin tasks.
        Raises ValueError if required DB settings are missing.
        """
        user = self.get_postgres_user()
        password = self.get_postgres_password()
        host = self.get_postgres_host()
        port = self.get_postgres_port()

        if not all([user, password, host, port]):
            missing = [
                name
                for name, val in [("USER", user), ("PASSWORD", password), ("HOST", host), ("PORT", port)]
                if not val
            ]
            raise ValueError(f"Missing required database settings ({', '.join(missing)}) for admin_dsn")

        return f"postgresql://{user}:{password}@{host}:{port}/postgres"

    @property
    def base_dsn(self) -> str:
        """Base DSN without a specific database name.
        Raises ValueError if required DB settings are missing.
        """
        user = self.get_postgres_user()
        password = self.get_postgres_password()
        host = self.get_postgres_host()
        port = self.get_postgres_port()

        if not all([user, password, host, port]):
            missing = [
                name
                for name, val in [("USER", user), ("PASSWORD", password), ("HOST", host), ("PORT", port)]
                if not val
            ]
            raise ValueError(f"Missing required database settings ({', '.join(missing)}) for base_dsn")

        return f"postgresql://{user}:{password}@{host}:{port}"

    def get_db_dsn(self, db_name: str | None = None) -> str:
        """Returns the DSN for a specific database name, or the default DB_NAME.
        Raises ValueError if required DB settings or the target db_name are missing.
        """
        target_db = db_name or self.get_postgres_db()
        if not target_db:
            raise ValueError("Missing target database name (either provide db_name or set DB_NAME env var)")
        base = self.base_dsn  # Use property
        return f"{base}/{target_db}"

    def get_run_mode(self) -> str:
        """Returns the run mode, defaulting to 'prod' if not set."""
        return os.getenv("RUN_MODE", "prod")

    def dev_mode(self) -> bool:
        """Returns True if the run mode is 'dev', False otherwise."""
        return self.get_run_mode() == "dev"
