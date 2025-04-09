import os
from typing import List, Optional
from urllib.parse import urlparse  # For basic URL validation

from dotenv import load_dotenv

# Load .env file variables into environment
load_dotenv(verbose=True)


class Settings:
    """Application configuration settings loaded from environment variables."""

    # --- Core Settings ---
    BACKEND_URL: Optional[str] = None
    POLICY_MODULE: str = "luthien_control.policies.examples.no_op.NoOpPolicy"
    # Comma-separated list of control policies for the beta framework
    CONTROL_POLICIES: Optional[str] = None

    # --- Database Settings ---
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: Optional[str] = None
    POSTGRES_HOST: Optional[str] = None
    POSTGRES_PORT: Optional[int] = 5432

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

    def get_openai_api_key(self) -> str | None:
        """Returns the OpenAI API key, if set."""
        return os.getenv("OPENAI_API_KEY")

    def get_policy_module(self) -> str:
        """Returns the configured policy module path."""
        return os.getenv("POLICY_MODULE", "luthien_control.policies.examples.no_op.NoOpPolicy")

    def get_control_policies_list(self) -> Optional[str]:
        """Returns the comma-separated list of control policies from env var."""
        return os.getenv("CONTROL_POLICIES")

    # --- Database settings Getters using os.getenv ---
    def get_postgres_user(self) -> str | None:
        return os.getenv("POSTGRES_USER")

    def get_postgres_password(self) -> str | None:
        return os.getenv("POSTGRES_PASSWORD")

    def get_postgres_host(self) -> str | None:
        return os.getenv("POSTGRES_HOST")

    def get_postgres_port(self) -> Optional[int]:
        port_str = os.getenv("POSTGRES_PORT")
        if port_str:
            try:
                return int(port_str)
            except ValueError:
                raise ValueError(f"Invalid POSTGRES_PORT: '{port_str}' is not an integer.")
        return None

    def get_postgres_db(self) -> str | None:
        return os.getenv("POSTGRES_DB")

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
        """Returns the DSN for a specific database name, or the default POSTGRES_DB.
        Raises ValueError if required DB settings or the target db_name are missing.
        """
        target_db = db_name or self.get_postgres_db()
        if not target_db:
            raise ValueError("Missing target database name (either provide db_name or set POSTGRES_DB env var)")
        base = self.base_dsn  # Use property
        return f"{base}/{target_db}"

    # --- Policy Settings --- #

    def get_request_policies(self) -> List[str]:
        """Returns a list of fully qualified request policy class names."""
        # TODO: Load from environment variable (e.g., REQUEST_POLICIES=...,...)
        # Example using existing policies:
        return [
            "luthien_control.policies.examples.no_op.NoOpPolicy",
            # "luthien_control.policies.examples.all_caps.AllCapsPolicy",
        ]

    def get_response_policies(self) -> List[str]:
        """Returns a list of fully qualified response policy class names."""
        # TODO: Load from environment variable (e.g., RESPONSE_POLICIES=...,...)
        return [
            "luthien_control.policies.examples.no_op.NoOpPolicy",
        ]

    # --- End Policy Settings --- #
