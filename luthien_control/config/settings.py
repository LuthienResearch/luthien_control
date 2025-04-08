import os
from urllib.parse import urlparse  # For basic URL validation

from dotenv import load_dotenv

# Load .env file variables into environment
load_dotenv(verbose=True)


# Removed BaseSettings inheritance
class Settings:
    """Application configuration settings loaded from environment variables."""

    # Removed type hints like HttpUrl, SecretStr, Field

    def get_backend_url(self) -> str:
        url = os.getenv("BACKEND_URL")
        if not url:
            raise ValueError("Missing required environment variable: BACKEND_URL")
        # Basic validation (can be enhanced)
        parsed = urlparse(url)
        if not all([parsed.scheme, parsed.netloc]):
            raise ValueError(f"Invalid BACKEND_URL format: {url}")
        return url

    def get_openai_api_key(self) -> str | None:
        # No SecretStr, just return the string or None
        return os.getenv("OPENAI_API_KEY")

    def get_policy_module(self) -> str:
        # Get value or use default
        return os.getenv("POLICY_MODULE", "luthien_control.policies.examples.no_op.NoOpPolicy")

    # --- Database settings Getters ---
    # Optional - required only for DB operations

    def get_postgres_user(self) -> str | None:
        return os.getenv("POSTGRES_USER")

    def get_postgres_password(self) -> str | None:
        # No SecretStr
        return os.getenv("POSTGRES_PASSWORD")

    def get_postgres_host(self) -> str | None:
        return os.getenv("POSTGRES_HOST")

    def get_postgres_port(self) -> int | None:
        port_str = os.getenv("POSTGRES_PORT")
        if port_str:
            try:
                return int(port_str)
            except ValueError:
                raise ValueError(f"Invalid POSTGRES_PORT: '{port_str}' is not an integer.")
        return None

    def get_postgres_db(self) -> str | None:
        return os.getenv("POSTGRES_DB")

    # --- Database DSN Helper Properties ---
    # Now use the getter methods instead of self.* attributes

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
        """Returns the DSN for a specific database name, or the default POSTGRES_DB.
        Raises ValueError if required DB settings or the target db_name are missing.
        """
        target_db = db_name or self.get_postgres_db()
        if not target_db:
            raise ValueError("Missing target database name (either provide db_name or set POSTGRES_DB env var)")
        # Call base_dsn property to ensure checks run and get the base string
        base = self.base_dsn
        return f"{base}/{target_db}"
