import os
import uuid
from pathlib import Path

import asyncpg
import psycopg2
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from luthien_control.config.settings import Settings
from luthien_control.main import app  # Import app directly
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Removed import of SettingsConfigDict
# Removed TestSettings class definition


# Removed integration_settings fixture


@pytest.fixture(autouse=True)
def override_settings_dependency(request):
    """Loads the correct .env file (.env or .env.test) based on test type
    (integration vs unit), instantiates Settings, and overrides the dependency.
    """
    settings_instance = None
    project_root = Path(__file__).parent.parent

    if request.node.get_closest_marker("integration"):
        env_file_path = project_root / ".env"
        print(f"\n[conftest] Loading INTEGRATION environment: {env_file_path}")
    else:
        env_file_path = project_root / ".env.test"
        print(f"\n[conftest] Loading UNIT TEST environment: {env_file_path}")

    if not env_file_path.exists():
        pytest.fail(f"Required environment file not found: {env_file_path}")

    # Load the selected .env file, overwriting existing environment variables
    loaded = load_dotenv(dotenv_path=env_file_path, override=True, verbose=True)
    if not loaded:
        print(f"[conftest] Warning: load_dotenv did not find variables in {env_file_path}")
    else:
        print(f"[conftest] Successfully loaded environment from {env_file_path}")

    # Now instantiate the Settings class. It will read from the loaded environment.
    try:
        settings_instance = Settings()
        # Perform a basic check
        _ = settings_instance.get_backend_url() # This will raise ValueError if missing
        print(f"[conftest] Settings instance created. BACKEND_URL: {settings_instance.get_backend_url()}")

    except Exception as e:
        pytest.fail(f"Failed to instantiate Settings after loading {env_file_path}: {e}")

    # Ensure we actually got an instance before proceeding
    if settings_instance is None:
        pytest.fail("Failed to obtain settings instance in override_settings_dependency")

    # Store the chosen settings instance in app.state (optional, but might be useful)
    app.state.test_settings = settings_instance

    # Store original overrides if any
    original_overrides = app.dependency_overrides.copy()
    original_state = getattr(app.state, "test_settings", None)

    def get_override_settings():
        # Return the instance created in this fixture
        return settings_instance

    app.dependency_overrides[Settings] = get_override_settings

    yield  # Run the test

    # Restore original overrides and state after test
    app.dependency_overrides = original_overrides
    app.state.test_settings = original_state
    # Optionally, could try to unload env vars here, but often not necessary/reliable


# Removed db_settings fixture


# Use pytest_asyncio.fixture for async fixtures
@pytest_asyncio.fixture(scope="session")
async def test_db_session(): # Removed db_settings parameter
    """
    Session-scoped fixture to create and manage a temporary PostgreSQL database for testing.
    Reads DB connection info from environment variables loaded by override_settings_dependency.

    Steps:
    1. Instantiates Settings to get DB connection details (admin DSN, target DB name).
    2. Connects to the default 'postgres' database using psycopg2 (sync).
    3. Creates a unique temporary database (e.g., 'test_db_<uuid>').
    4. Reads the schema from 'db/schema_v1.sql'.
    5. Connects to the temporary database using asyncpg (async).
    6. Applies the schema to the temporary database.
    7. Yields the DSN (connection string) for the temporary database.
    8. Tears down by dropping the temporary database using psycopg2 (sync).
    """
    # Instantiate Settings here. It will use the env vars loaded by the
    # autouse override_settings_dependency fixture (specifically .env for session scope)
    # Note: This assumes the session scope aligns with loading .env via the override.
    # If override logic changes significantly, this might need adjustment.
    try:
        # We need the main .env settings for DB creation, assume override_settings_dependency
        # handles loading .env correctly for the session scope start.
        # A specific load here might be safer if override becomes test-scoped only.
        load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True, verbose=True)
        db_settings = Settings()
        # Validate required settings are present
        _ = db_settings.admin_dsn # Will raise if settings missing
        _ = db_settings.get_postgres_db() # Check default DB name exists if needed later
        print("[test_db_session] Settings loaded for DB operations.")
    except Exception as e:
        pytest.fail(f"[test_db_session] Failed to load Settings for DB setup: {e}. Ensure .env has required POSTGRES_* vars.")

    temp_db_name = f"test_db_{uuid.uuid4().hex}"
    print(f"\nCreating temporary test database: {temp_db_name}")

    # --- Database Creation (using psycopg2 - sync) ---
    conn_admin = None
    try:
        admin_dsn = db_settings.admin_dsn # Use property from the instantiated Settings
        conn_admin = psycopg2.connect(dsn=admin_dsn)
        conn_admin.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with conn_admin.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (temp_db_name,))
            if cursor.fetchone():
                print(f"Warning: Database {temp_db_name} already exists. Attempting to drop and recreate.")
                cursor.execute(f'DROP DATABASE "{temp_db_name}"')
            print(f"Executing CREATE DATABASE {temp_db_name}")
            cursor.execute(f'CREATE DATABASE "{temp_db_name}"')
        print(f"Database {temp_db_name} created successfully.")
    except psycopg2.Error as e:
        pytest.fail(f"Failed to create temporary database {temp_db_name} using DSN {admin_dsn[:admin_dsn.find('@')]}...: {e}") # Avoid logging password
    finally:
        if conn_admin:
            conn_admin.close()

    # --- Schema Application (using asyncpg - async) ---
    conn_test_db = None
    try:
        # Use the get_db_dsn method from the instantiated Settings
        temp_db_dsn = db_settings.get_db_dsn(temp_db_name)
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
        pytest.fail(f"Failed to apply schema to {temp_db_name} using DSN {temp_db_dsn[:temp_db_dsn.find('@')]}...: {e}") # Avoid logging password
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
        admin_dsn_drop = db_settings.admin_dsn # Use property again
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
    The settings used by the app will be determined by override_settings_dependency.
    """
    from fastapi.testclient import TestClient

    # TestClient handles startup/shutdown implicitly when used as context manager
    with TestClient(app) as test_client:
        yield test_client
