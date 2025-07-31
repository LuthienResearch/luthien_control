import os
import uuid
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from dotenv import load_dotenv
from luthien_control.core.dependency_container import DependencyContainer

# Import centralized type alias
from luthien_control.main import app
from luthien_control.settings import Settings
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


# NO REAL DATABASE FIXTURES - All databases are mocked


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


@pytest.fixture()
def client_with_admin_mock(mock_admin_service_for_startup):
    """Pytest fixture for the FastAPI TestClient with admin service mocked.
    Use this fixture for tests that need to avoid database calls during startup.
    """
    from fastapi.testclient import TestClient

    # The mock_admin_service_for_startup fixture will be active during this client's lifespan
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_settings() -> MagicMock:
    """Provides a mock Settings instance."""
    settings = MagicMock(spec=Settings)
    # Add common default return values if needed by most tests
    settings.get_top_level_policy_name.return_value = "test_policy"
    return settings


@pytest.fixture
def mock_http_client() -> AsyncMock:
    """Provides a mock httpx.AsyncClient instance."""
    client = AsyncMock(spec=httpx.AsyncClient)
    return client


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Provides a mock SQLAlchemy AsyncSession instance."""
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def mock_admin_auth_service() -> AsyncMock:
    """Provides a mock admin auth service."""
    from luthien_control.admin.auth import AdminAuthService

    service = AsyncMock(spec=AdminAuthService)
    # Mock the ensure_default_admin method to be a no-op
    service.ensure_default_admin = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_db_session_factory(mock_db_session: AsyncMock) -> MagicMock:
    """Provides a mock database session factory context manager."""
    # Use a synchronous context manager mock that yields the async session mock
    mock_factory = MagicMock()

    # Create a mock async context manager
    mock_async_context_manager = AsyncMock()
    mock_async_context_manager.__aenter__.return_value = mock_db_session
    mock_async_context_manager.__aexit__.return_value = None  # Or return an awaitable if needed

    # Configure the factory mock to return the async context manager when called
    mock_factory.return_value = mock_async_context_manager

    return mock_factory


@pytest.fixture
def mock_container(
    mock_settings: MagicMock,
    mock_http_client: AsyncMock,
    mock_db_session_factory: MagicMock,
) -> MagicMock:
    """Provides a mock DependencyContainer instance."""
    container = MagicMock(spec=DependencyContainer)
    container.settings = mock_settings
    container.http_client = mock_http_client
    container.db_session_factory = mock_db_session_factory
    return container


@pytest.fixture
def mock_api_key_data() -> Dict[str, Any]:
    """Provides sample data for a ClientApiKey."""
    return {
        "id": uuid.uuid4(),
        "name": "Test Key",
        "hashed_api_key": "hashed_test_key_value",
        "is_active": True,
        "description": "A key for testing",
    }


# --- Fixtures for Overriding Dependencies ---


@pytest.fixture()
def mock_admin_service_for_startup():
    """Mock the admin auth service's ensure_default_admin method during app startup to prevent database calls."""

    # Create a simple async no-op function with proper signature
    async def mock_ensure_default_admin(self, db):
        """Mock ensure_default_admin to be a no-op."""
        pass

    # Apply patch for this test
    with patch("luthien_control.admin.auth.AdminAuthService.ensure_default_admin", mock_ensure_default_admin):
        yield


@pytest.fixture()
def admin_client_with_full_mocking():
    """
    Specialized fixture for admin router tests that need complete database mocking.
    Only use this for tests that absolutely need to avoid all database connections.
    """
    from fastapi.testclient import TestClient
    from luthien_control.core.dependency_container import DependencyContainer

    # Mock the entire app initialization to prevent database connections
    mock_container = MagicMock(spec=DependencyContainer)

    # Create a proper async context manager for db_session_factory
    mock_session = AsyncMock()
    mock_async_cm = AsyncMock()
    mock_async_cm.__aenter__.return_value = mock_session
    mock_async_cm.__aexit__.return_value = None

    mock_factory = MagicMock(return_value=mock_async_cm)
    mock_container.db_session_factory = mock_factory

    # Mock http_client
    mock_http_client = AsyncMock()
    mock_http_client.aclose = AsyncMock()
    mock_container.http_client = mock_http_client

    async def mock_initialize_dependencies(settings):
        return mock_container

    # Mock admin service
    async def mock_ensure_default_admin(self, db):
        pass

    with patch("luthien_control.main.initialize_app_dependencies", mock_initialize_dependencies):
        with patch("luthien_control.admin.auth.AdminAuthService.ensure_default_admin", mock_ensure_default_admin):
            with TestClient(app) as test_client:
                yield test_client


@pytest.fixture
def database_mocking():
    """
    Opt-in fixture to mock database connections for tests that need it.
    Use this fixture when your test should not touch real databases.
    """
    # Mock database connections at multiple levels
    with patch("luthien_control.db.database_async.create_db_engine") as mock_create_engine:
        # Mock the database engine creation to prevent ANY database connections
        mock_engine = AsyncMock()
        mock_create_engine.return_value = mock_engine

        # Mock SQLAlchemy engine creation at all levels
        with patch("sqlalchemy.ext.asyncio.create_async_engine") as mock_sa_engine:
            mock_sa_engine.return_value = AsyncMock()

            # Mock SQLModel table creation
            with patch("sqlmodel.SQLModel.metadata.create_all") as mock_create_all:
                mock_create_all.return_value = AsyncMock()

                # Mock async session creation
                with patch("sqlalchemy.ext.asyncio.async_sessionmaker") as mock_sessionmaker:
                    mock_sessionmaker.return_value = AsyncMock()

                    yield  # Run the test with database mocking


@pytest.fixture
def app_startup_mocking():
    """
    Opt-in fixture to mock app startup dependencies for tests that use TestClient
    but don't want real dependency initialization.
    """
    with patch("luthien_control.main.initialize_app_dependencies") as mock_init_deps:
        # Mock the app dependency initialization
        mock_container = MagicMock()
        mock_container.db_session_factory = AsyncMock()
        mock_init_deps.return_value = mock_container

        with patch("luthien_control.admin.auth.AdminAuthService.ensure_default_admin") as mock_admin:
            # Mock admin service to prevent DB calls during startup
            mock_admin.return_value = AsyncMock()

            yield mock_container


@pytest.fixture
def full_app_mocking(database_mocking, app_startup_mocking):
    """
    Combines database mocking and app startup mocking for tests that need both.
    Use this for tests that use TestClient but should not touch databases.
    """
    yield app_startup_mocking


# --- Other Helper Fixtures ---
