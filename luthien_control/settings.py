import os
from typing import Optional
from urllib.parse import urlparse

from dotenv import load_dotenv

# Load .env file variables into environment
load_dotenv(verbose=True)


class Settings:
    """Application configuration settings.

    This class encapsulates all configuration settings for the Luthien Control
    application. Settings are primarily loaded from environment variables.
    A .env file can be used to specify these variables during development.

    Attributes:
        BACKEND_URL: The URL of the backend service the proxy will forward requests to.
        DB_SERVER: The database server hostname or IP address.
        DB_USER: The username for database connection.
        DB_PASSWORD: The password for database connection.
        DB_NAME: The name of the database.
        DB_HOST: The database host (can be different from DB_SERVER for specific setups).
        DB_PORT: The port number for the database connection.
        OPENAI_API_KEY: The API key for accessing OpenAI services.
    """

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
        """Get the backend URL from environment variables.

        Returns:
            The backend URL as a string if set and valid, otherwise None.

        Raises:
            ValueError: If the BACKEND_URL is set but has an invalid format.
        """
        url = os.getenv("BACKEND_URL")
        if url:
            # Basic validation (can be enhanced)
            parsed = urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                raise ValueError(f"Invalid BACKEND_URL format: {url}")
        return url

    def get_database_url(self) -> Optional[str]:
        """Get the primary database URL from environment variables.

        Returns:
            The DATABASE_URL string if set, otherwise None.
        """
        return os.getenv("DATABASE_URL")

    def get_openai_api_key(self) -> str | None:
        """Get the OpenAI API key from environment variables.

        Returns:
            The OpenAI API key if set, otherwise None.
        """
        return os.getenv("OPENAI_API_KEY")

    def get_top_level_policy_name(self) -> str:
        """Get the name of the top-level policy instance to load.

        Returns:
            The value of the TOP_LEVEL_POLICY_NAME environment variable,
            defaulting to "root" if not set.
        """
        return os.getenv("TOP_LEVEL_POLICY_NAME", "root")

    # --- Database settings Getters using os.getenv ---
    def get_postgres_user(self) -> str | None:
        """Get the PostgreSQL username from environment variables."""
        return os.getenv("DB_USER")

    def get_postgres_password(self) -> str | None:
        """Get the PostgreSQL password from environment variables."""
        return os.getenv("DB_PASSWORD")

    def get_postgres_db(self) -> str | None:
        """Get the PostgreSQL database name from environment variables."""
        return os.getenv("DB_NAME")

    def get_postgres_host(self) -> str | None:
        """Get the PostgreSQL host from environment variables."""
        return os.getenv("DB_HOST")

    def get_postgres_port(self) -> int | None:
        """Get the PostgreSQL port from environment variables.

        Returns:
            The PostgreSQL port as an integer if set and valid, otherwise None.

        Raises:
            ValueError: If DB_PORT is set but is not a valid integer.
        """
        port_str = os.getenv("DB_PORT")
        if port_str is None:
            return None
        try:
            return int(port_str)
        except ValueError:
            raise ValueError("DB_PORT environment variable must be an integer.")

    # --- DB Pool Size Getters ---
    def get_main_db_pool_min_size(self) -> int:
        """Get the minimum connection pool size for the main database.

        Returns:
            The minimum pool size, defaulting to 1 if not set or invalid.

        Raises:
            ValueError: If MAIN_DB_POOL_MIN_SIZE is set but is not a valid integer.
        """
        try:
            return int(os.getenv("MAIN_DB_POOL_MIN_SIZE", "1"))
        except ValueError:
            raise ValueError("MAIN_DB_POOL_MIN_SIZE environment variable must be an integer.")

    def get_main_db_pool_max_size(self) -> int:
        """Get the maximum connection pool size for the main database.

        Returns:
            The maximum pool size, defaulting to 10 if not set or invalid.

        Raises:
            ValueError: If MAIN_DB_POOL_MAX_SIZE is set but is not a valid integer.
        """
        try:
            return int(os.getenv("MAIN_DB_POOL_MAX_SIZE", "10"))
        except ValueError:
            raise ValueError("MAIN_DB_POOL_MAX_SIZE environment variable must be an integer.")

    # --- Logging Settings --- # Added based on grep results
    def get_log_level(self, default: str = "INFO") -> str:
        """Get the configured log level from environment variables.

        Args:
            default: The default log level to use if LOG_LEVEL is not set.
                     Defaults to "INFO".

        Returns:
            The log level string, converted to uppercase.
        """
        return os.getenv("LOG_LEVEL", default).upper()

    # --- Database DSN Helper Properties using Getters ---
    @property
    def admin_dsn(self) -> str:
        """Construct the DSN for connecting to the default 'postgres' database.

        This DSN is typically used for administrative tasks like creating
        or dropping databases.

        Returns:
            The admin DSN string.

        Raises:
            ValueError: If any of the required database settings (user, password,
                        host, port) are not configured via environment variables.
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
        """Construct the base DSN without a specific database name.

        This DSN forms the common part of database connection strings for
        the configured server.

        Returns:
            The base DSN string.

        Raises:
            ValueError: If any of the required database settings (user, password,
                        host, port) are not configured via environment variables.
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
        """Construct the DSN for a specific database, or the default database.

        If `db_name` is provided, it is used. Otherwise, the method attempts
        to use the database name configured by the DB_NAME environment variable.

        Args:
            db_name: Optional specific database name to use in the DSN.

        Returns:
            The full DSN string for connecting to the target database.

        Raises:
            ValueError: If any required base DSN settings are missing, or if
                        neither `db_name` is provided nor DB_NAME is set.
        """
        target_db = db_name or self.get_postgres_db()
        if not target_db:
            raise ValueError("Missing target database name (either provide db_name or set DB_NAME env var)")
        base = self.base_dsn  # Use property
        return f"{base}/{target_db}"
