import os
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, Optional
from unittest.mock import AsyncMock, MagicMock

import fastapi
import httpx
import psycopg2
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from dotenv import load_dotenv
from luthien_control.config.settings import Settings
from luthien_control.core.response_builder.interface import ResponseBuilder
from luthien_control.core.transaction_context import TransactionContext
from luthien_control.db.sqlmodel_models import ClientApiKey
from luthien_control.main import app
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy.ext.asyncio import AsyncSession

# --- Command Line Option ---


def pytest_addoption(parser):
    parser.addoption(
        "--e2e-target-url",
        action="store",
        default=None,
        help="URL of a deployed proxy server to target for E2E tests. If not provided, a local server will be started.",
    )


@pytest.fixture(autouse=True)
def override_settings_dependency(request):
    """AUTOUSE: Loads the correct .env file (.env.test or .env) based on markers,
    then applies test-specific environment variables from the 'envvars' marker.
    SKIPS execution if the test is marked 'e2e'.
    """
    if request.node.get_closest_marker("e2e"):
        print("\n[conftest] Skipping override_settings_dependency for e2e test.")
        yield  # Still need to yield for autouse fixture
        return  # Exit early

    project_root = Path(__file__).parent.parent
    original_environ = os.environ.copy()  # Store original environment

    # 1. Load Base Environment File
    if request.node.get_closest_marker("integration"):
        env_file_path = project_root / ".env"
        print(f"\n[conftest] Loading INTEGRATION environment: {env_file_path}")
    else:
        env_file_path = project_root / ".env.test"
        print(f"\n[conftest] Loading UNIT TEST environment: {env_file_path}")

    if not env_file_path.exists():
        if request.node.get_closest_marker("integration"):
            pytest.fail(f"Required environment file not found for integration test: {env_file_path}")
        else:
            print(
                f"[conftest] Warning: Unit test environment file not found: {env_file_path}. "
                f"Proceeding with system env."
            )
            # Proceed without loading file, apply marker vars below
    else:
        loaded = load_dotenv(dotenv_path=env_file_path, override=True, verbose=True)
        if loaded:
            print(f"[conftest] Successfully loaded environment from {env_file_path}")
        else:
            print(f"[conftest] Warning: load_dotenv did not find variables in {env_file_path}")

    yield  # Allow test to run

    # 3. Restore Original Environment
    print("[conftest] Restoring original environment variables.")
    os.environ.clear()
    os.environ.update(original_environ)


# Use pytest_asyncio.fixture for async fixtures
@pytest_asyncio.fixture(scope="session")
async def db_session_fixture():
    """
    Session-scoped fixture to create and manage a temporary PostgreSQL database for testing.
    Reads DB connection info from environment variables loaded by override_settings_dependency.
    """
    # Instantiate Settings here. It will use the env vars loaded by the
    # autouse override_settings_dependency fixture.
    db_settings = None  # Initialize
    try:
        # Explicitly load .env here for session-scoped DB setup, as the autouse
        # fixture might load .env.test if *any* non-integration test triggers it first.
        # This ensures DB creation always uses the main credentials.
        main_env_path = Path(__file__).parent.parent / ".env"
        print(f"[db_session_fixture] Explicitly loading environment for DB setup: {main_env_path}")
        load_dotenv(dotenv_path=main_env_path, override=True, verbose=True)
        db_settings = Settings()
        _ = db_settings.admin_dsn  # Will raise if settings missing
        print("[db_session_fixture] Settings loaded for DB operations.")
    except Exception as e:
        pytest.fail(
            f"[db_session_fixture] Failed to load Settings for DB setup: {e}. Ensure .env has required DB_* vars."
        )

    temp_db_name = f"test_db_{uuid.uuid4().hex}"
    print(f"\nCreating temporary test database: {temp_db_name}")

    # --- Database Creation (using psycopg2 - sync) ---
    conn_admin = None
    try:
        admin_dsn = db_settings.admin_dsn
        conn_admin = psycopg2.connect(dsn=admin_dsn)
        conn_admin.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with conn_admin.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (temp_db_name,))
            if cursor.fetchone():
                print(f"Warning: Database {temp_db_name} already exists. Attempting to drop and recreate.")
                cursor.execute(f'DROP DATABASE IF EXISTS "{temp_db_name}" WITH (FORCE)')
            print(f"Executing CREATE DATABASE {temp_db_name}")
            cursor.execute(f'CREATE DATABASE "{temp_db_name}"')
        print(f"Database {temp_db_name} created successfully.")
    except psycopg2.Error as e:
        pytest.fail(
            f"Failed to create temporary database {temp_db_name} using DSN {admin_dsn[: admin_dsn.find('@')]}...: {e}"
        )
    finally:
        if conn_admin:
            conn_admin.close()

    # --- Schema Application (using Alembic - sync) ---
    temp_db_dsn = db_settings.get_db_dsn(temp_db_name)
    try:
        print(f"Applying Alembic migrations to {temp_db_name}...")
        alembic_cfg_path = Path(__file__).parent.parent / "alembic.ini"
        if not alembic_cfg_path.is_file():
            pytest.fail(f"Alembic config file not found at: {alembic_cfg_path}")

        alembic_cfg = Config(str(alembic_cfg_path))
        # Tell Alembic to use the temporary database's connection string
        # The sqlalchemy.url key in alembic.ini is used by default
        alembic_cfg.set_main_option("sqlalchemy.url", temp_db_dsn.replace("+asyncpg", "+psycopg2"))

        # Ensure the script location is correctly set (relative to alembic.ini)
        script_location = Path(alembic_cfg.get_main_option("script_location", "."))
        if not (alembic_cfg_path.parent / script_location).exists():
            pytest.fail(f"Alembic script location not found: {alembic_cfg_path.parent / script_location}")
        alembic_cfg.set_main_option("script_location", str(script_location))

        command.upgrade(alembic_cfg, "head")
        print(f"Alembic migrations applied successfully to {temp_db_name}.")

    except Exception as e:
        pytest.fail(
            f"Failed to apply Alembic migrations to {temp_db_name} "
            f"using DSN {temp_db_dsn[: temp_db_dsn.find('@')]}...: {e}"
        )

    # --- Yield DSN for Tests ---
    print(f"Yielding DSN for tests: {temp_db_dsn}")
    yield temp_db_dsn

    # --- Teardown: Drop Database (using psycopg2 - sync) ---
    print(f"\nDropping temporary test database: {temp_db_name}...")
    conn_admin_drop = None
    try:
        admin_dsn_drop = db_settings.admin_dsn
        conn_admin_drop = psycopg2.connect(dsn=admin_dsn_drop)
        conn_admin_drop.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with conn_admin_drop.cursor() as cursor:
            cursor.execute(
                """
                SELECT pg_terminate_backend(pg_stat_activity.pid)
                FROM pg_stat_activity
                WHERE pg_stat_activity.datname = %s
                  AND pid <> pg_backend_pid();
            """,
                (temp_db_name,),
            )
            print(f"Terminated any existing connections to {temp_db_name}.")
            cursor.execute(f'DROP DATABASE "{temp_db_name}"')
        print(f"Database {temp_db_name} dropped successfully.")
    except psycopg2.Error as e:
        print(f"Error dropping test database {temp_db_name}: {e}")
    finally:
        if conn_admin_drop:
            conn_admin_drop.close()


@pytest.fixture(scope="session")
def client():
    """Pytest fixture for the FastAPI TestClient.
    Uses the main 'app' imported from luthien_control.main.
    Ensures lifespan events are handled correctly by TestClient.
    Relies on the autouse override_settings_dependency to set env vars first.
    """
    from fastapi.testclient import TestClient

    # TestClient handles startup/shutdown implicitly when used as context manager
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_builder() -> MagicMock:
    """Provides a mock ResponseBuilder instance."""
    builder = MagicMock(spec=ResponseBuilder)
    builder.build_response.return_value = MagicMock(spec=fastapi.Response)
    return builder


# --- End Moved Fixtures --- #

# --- Added Mock Fixtures for Dependencies --- #

# Define the type alias if not already globally available
ApiKeyLookupFunc = Callable[[str], Awaitable[Optional[ClientApiKey]]]


@pytest.fixture
def mock_settings() -> MagicMock:
    """Provides a mock Settings object."""
    settings = MagicMock(spec=Settings)
    # Add specific return values if needed by tests using this fixture
    # e.g., settings.get_backend_url.return_value = "http://mock-backend.com"
    return settings


@pytest.fixture
def mock_http_client() -> AsyncMock:
    """Provides a mock httpx.AsyncClient."""
    client = AsyncMock(spec=httpx.AsyncClient)
    # Add specific mock responses or behaviors if needed
    # e.g., client.send.return_value = AsyncMock(spec=httpx.Response, status_code=200)
    return client


@pytest.fixture
def mock_api_key_lookup() -> AsyncMock:
    """Provides a mock api_key_lookup function."""
    lookup = AsyncMock(spec=ApiKeyLookupFunc)
    # Add specific return values for mock keys if needed
    # e.g., async def side_effect(key_value): if key_value == 'valid': return MagicMock(spec=ClientApiKey); return None
    # lookup.side_effect = side_effect
    return lookup


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Provides a mock SQLAlchemy AsyncSession."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_api_key_data() -> Dict[str, Any]:
    """Provides sample data for an API key."""
    return MagicMock(spec=ClientApiKey)


@pytest.fixture
def mock_transaction_context() -> MagicMock:
    """Provides a mock TransactionContext."""
    return MagicMock(spec=TransactionContext)
