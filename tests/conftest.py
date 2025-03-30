import os
import uuid
from pathlib import Path

import asyncpg
import psycopg2
import pytest
import pytest_asyncio  # Import pytest_asyncio
from luthien_control.config.settings import Settings, get_settings
from luthien_control.proxy.server import app as fastapi_app  # Import the FastAPI app
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT


@pytest.fixture(scope="session")
def app():
    """Fixture to provide the FastAPI app instance."""
    return fastapi_app


@pytest.fixture(scope="session")
def unit_settings() -> Settings:
    """Fixture to load settings specifically for unit tests (.env.test)."""
    # Ensure APP_ENV is set correctly for unit tests
    original_env = os.environ.get("APP_ENV")
    os.environ["APP_ENV"] = "test"

    # Clear the cache for get_settings before calling it
    get_settings.cache_clear()
    settings = get_settings()

    # Restore original APP_ENV if it existed
    if original_env is None:
        del os.environ["APP_ENV"]
    else:
        os.environ["APP_ENV"] = original_env

    # Clear cache again after restoring env (optional but clean)
    get_settings.cache_clear()

    assert settings.BACKEND_URL.host == "mock-backend.test", (
        "Unit tests should use the mock backend URL from .env.test"
    )
    return settings


@pytest.fixture(scope="session")
def integration_settings() -> Settings:
    """Fixture to load settings for integration tests (.env).
    Skips tests if OPENAI_API_KEY is not found.
    """
    # Ensure APP_ENV is NOT test for integration tests
    original_env = os.environ.get("APP_ENV")
    if original_env == "test":
        del os.environ["APP_ENV"]

    # Clear cache and get settings (should load from .env)
    get_settings.cache_clear()
    settings = get_settings()

    # Restore original APP_ENV if needed
    if original_env is not None:
        os.environ["APP_ENV"] = original_env

    # Clear cache again
    get_settings.cache_clear()

    if not settings.OPENAI_API_KEY:
        pytest.skip("Skipping integration test: OPENAI_API_KEY not found in .env")

    assert settings.BACKEND_URL.host != "127.0.0.1", (
        "Integration tests should use the real backend URL from .env"
    )
    return settings


# Fixture to override settings dependency in FastAPI app for testing
@pytest.fixture(autouse=True)  # Apply this automatically to relevant tests
def override_settings_dependency(app, request):
    """Overrides the get_settings dependency based on test markers."""
    if request.node.get_closest_marker("integration"):
        # Use integration settings for integration tests
        print("\n[Fixture] Using integration_settings for test")
        app.dependency_overrides[get_settings] = lambda: request.getfixturevalue(
            "integration_settings"
        )
        yield
        del app.dependency_overrides[get_settings]
        print("[Fixture] Cleared settings override for integration_settings")
    elif request.node.get_closest_marker("unit"):
        # Use unit settings for unit tests
        print("\n[Fixture] Using unit_settings for test (unit marker found)")
        app.dependency_overrides[get_settings] = lambda: request.getfixturevalue(
            "unit_settings"
        )
        yield
        del app.dependency_overrides[get_settings]
        print("[Fixture] Cleared settings override for unit_settings")
    else:
        # Default to unit settings if no specific marker is found
        print("\n[Fixture] Using unit_settings for test (default/no marker)")
        app.dependency_overrides[get_settings] = lambda: request.getfixturevalue(
            "unit_settings"
        )
        yield
        del app.dependency_overrides[get_settings]
        print("[Fixture] Cleared settings override for unit_settings (default)")


# Add a unit marker definition implicitly if needed
# Or rely on the absence of 'integration' marker


@pytest.fixture(scope="session")
def db_settings() -> Settings:
    """Fixture to load database settings from environment variables via get_settings."""
    try:
        # Use the existing get_settings function, which handles .env loading
        # Assume APP_ENV is not 'test' for db setup, relying on .env
        original_env = os.getenv("APP_ENV")
        if original_env == "test":
            del os.environ["APP_ENV"]

        get_settings.cache_clear()  # Clear cache before getting settings
        settings = get_settings()

        # Restore original APP_ENV if needed
        if original_env is not None:
            os.environ["APP_ENV"] = original_env
        get_settings.cache_clear()  # Clear cache after restoring

        # Basic check to ensure critical settings are loaded
        assert all(
            [
                settings.POSTGRES_USER,
                settings.POSTGRES_PASSWORD,
                settings.POSTGRES_HOST,
                settings.POSTGRES_PORT,
                settings.POSTGRES_DB,
            ]
        )
        return settings
    except Exception as e:
        pytest.fail(
            f"Failed to load database settings via get_settings: {e}. Ensure POSTGRES_* env vars are set or available in .env"
        )


# Use pytest_asyncio.fixture for async fixtures
@pytest_asyncio.fixture(scope="session")
async def test_db_session(db_settings: Settings):
    """
    Session-scoped fixture to create and manage a temporary PostgreSQL database for testing.

    Steps:
    1. Connects to the default 'postgres' database using psycopg2 (sync).
    2. Creates a unique temporary database (e.g., 'test_db_<uuid>').
    3. Reads the schema from 'db/schema_v1.sql'.
    4. Connects to the temporary database using asyncpg (async).
    5. Applies the schema to the temporary database.
    6. Yields the DSN (connection string) for the temporary database.
    7. Tears down by dropping the temporary database using psycopg2 (sync).
    """
    temp_db_name = f"test_db_{uuid.uuid4().hex}"
    print(f"\nCreating temporary test database: {temp_db_name}")

    # --- Database Creation (using psycopg2 - sync) ---
    conn_admin = None
    try:
        # Use the admin_dsn property from the Settings object
        conn_admin = psycopg2.connect(dsn=db_settings.admin_dsn)
        conn_admin.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with conn_admin.cursor() as cursor:
            # Check if db exists first (optional, but avoids error noise if tests are interrupted)
            cursor.execute(
                "SELECT 1 FROM pg_database WHERE datname = %s", (temp_db_name,)
            )
            if cursor.fetchone():
                print(
                    f"Warning: Database {temp_db_name} already exists. Attempting to drop and recreate."
                )
                cursor.execute(
                    f'DROP DATABASE "{temp_db_name}"'
                )  # Use quotes for safety

            print(f"Executing CREATE DATABASE {temp_db_name}")
            cursor.execute(f'CREATE DATABASE "{temp_db_name}"')
        print(f"Database {temp_db_name} created successfully.")
    except psycopg2.Error as e:
        pytest.fail(f"Failed to create temporary database {temp_db_name}: {e}")
    finally:
        if conn_admin:
            conn_admin.close()

    # --- Schema Application (using asyncpg - async) ---
    # Use the get_db_dsn method from the Settings object
    temp_db_dsn = db_settings.get_db_dsn(temp_db_name)
    conn_test_db = None
    try:
        # Construct path to schema relative to this conftest.py file
        schema_path = Path(__file__).parent.parent / "db" / "schema_v1.sql"
        if not schema_path.is_file():
            pytest.fail(f"Schema file not found at: {schema_path}")

        print(f"Applying schema from {schema_path} to {temp_db_name}...")
        schema_sql = schema_path.read_text()

        conn_test_db = await asyncpg.connect(dsn=temp_db_dsn)
        await conn_test_db.execute(schema_sql)
        print(f"Schema applied successfully to {temp_db_name}.")

    except (asyncpg.PostgresError, FileNotFoundError, OSError) as e:
        pytest.fail(f"Failed to apply schema to {temp_db_name}: {e}")
    finally:
        if conn_test_db and not conn_test_db.is_closed():
            await conn_test_db.close()

    # --- Yield DSN for Tests ---
    print(f"Yielding DSN for tests: {temp_db_dsn}")
    yield temp_db_dsn  # Provide the DSN to the tests

    # --- Teardown: Drop Database (using psycopg2 - sync) ---
    print(f"\nDropping temporary test database: {temp_db_name}...")
    conn_admin_drop = None
    try:
        # Use the admin_dsn property from the Settings object
        conn_admin_drop = psycopg2.connect(dsn=db_settings.admin_dsn)
        conn_admin_drop.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with conn_admin_drop.cursor() as cursor:
            # Force disconnect users - crucial if tests left connections open
            cursor.execute(
                f"""
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
        # Log error but don't fail the entire test run during teardown if possible
        print(f"Error dropping test database {temp_db_name}: {e}")
    finally:
        if conn_admin_drop:
            conn_admin_drop.close()
