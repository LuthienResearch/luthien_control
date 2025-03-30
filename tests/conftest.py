import os
import uuid
from pathlib import Path

import asyncpg
import psycopg2
import pytest
import pytest_asyncio
from luthien_control.config.settings import Settings
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from pydantic import HttpUrl, Field, SecretStr
# Import SettingsConfigDict for overriding and TestSettings definition
from pydantic_settings import BaseSettings, SettingsConfigDict


# Remove monkeypatch_session fixture if no longer needed
# @pytest.fixture(scope='session')
# def monkeypatch_session():
#     """Session-scoped monkeypatch."""
#     from _pytest.monkeypatch import MonkeyPatch
#     m = MonkeyPatch()
#     yield m
#     m.undo()


# --- Define TestSettings inheriting from main Settings --- 
class TestSettings(Settings):
    """Test-specific settings loading ONLY from .env.test."""
    
    # Define model_config to ONLY load .env.test using absolute path
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).parent.parent / ".env.test"), 
        extra='ignore'
    )
    # Fields are inherited from the main Settings class


@pytest.fixture(scope="session")
def integration_settings() -> Settings:
    """Fixture providing Settings loaded explicitly from .env."""
    try:
        config_override = SettingsConfigDict(env_file='.env', extra='ignore') # Be explicit
        settings = Settings(_settings_config_override=config_override)

        # Assert that the loaded URL is NOT the mock one
        assert settings.BACKEND_URL.host != "mock-backend.test", (
            f"Integration tests should load from .env, but BACKEND_URL is the mock URL: '{settings.BACKEND_URL}'"
        )
        return settings
    except Exception as e:
        pytest.fail(f"Failed to load integration_settings from .env: {e}")


# Override the Settings class itself
@pytest.fixture(autouse=True)
def override_settings_dependency(request):
    """Overrides the Settings dependency based on test markers."""
    from luthien_control.main import app
    settings_instance = None

    if request.node.get_closest_marker("integration"):
        # For integration tests, get the correctly configured Settings instance
        settings_instance = request.getfixturevalue("integration_settings")
    else:
        # For unit tests, instantiate our TestSettings class directly
        env_test_path = Path(__file__).parent.parent / ".env.test"
        if not env_test_path.exists():
            pytest.fail(f"Unit test setup failed: .env.test not found at {env_test_path}")
        try:
            settings_instance = TestSettings() 
        except Exception as e:
             pytest.fail(f"Failed to instantiate TestSettings for unit test: {e}")

    # Ensure we actually got an instance before proceeding
    if settings_instance is None:
        pytest.fail("Failed to obtain settings instance in override_settings_dependency")

    # Store original overrides if any (though likely none)
    original_overrides = app.dependency_overrides.copy()

    def get_override_settings(): 
        # This function now just returns the instance we already created/fetched
        return settings_instance

    app.dependency_overrides[Settings] = get_override_settings # Override with our chosen instance
    yield # Run the test
    # Restore original overrides after test
    app.dependency_overrides = original_overrides


@pytest.fixture(scope="session")
def db_settings() -> Settings:
    """Fixture providing database connection Settings loaded explicitly from .env."""
    try:
        # Explicitly load ONLY .env for database settings
        config_override = SettingsConfigDict(env_file='.env', extra='ignore') # Be explicit
        settings_loaded = Settings(_settings_config_override=config_override)

        assert all(
            [
                settings_loaded.POSTGRES_USER,
                settings_loaded.POSTGRES_PASSWORD,
                settings_loaded.POSTGRES_HOST,
                settings_loaded.POSTGRES_PORT,
                settings_loaded.POSTGRES_DB,
            ]
        ), "Database configuration settings missing. Ensure POSTGRES_* vars are in .env."
        return settings_loaded

    except Exception as e:
        pytest.fail(
            f"Failed to load db_settings from .env: {e}"
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


@pytest.fixture(scope="session") # Scope might be session if app doesn't change
def client():
    """Pytest fixture for the FastAPI TestClient.
    Uses the main 'app' imported from luthien_control.main.
    Ensures lifespan events are handled correctly by TestClient.
    """
    # Ensure httpx is installed for TestClient
    from luthien_control.main import app # Import here to avoid top-level side effects if any
    from fastapi.testclient import TestClient

    # TestClient handles startup/shutdown implicitly when used as context manager
    with TestClient(app) as test_client:
        yield test_client
