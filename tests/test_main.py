from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi.testclient import TestClient


def test_read_root(client: TestClient):
    """Test the root endpoint '/'."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Luthien Control Proxy is running."}


def test_health_check(client: TestClient):
    """Test the health check endpoint '/health'."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_lifespan_success_path(mocker):
    """Test the successful startup and shutdown sequence of the app lifespan."""
    # 1. Mock dependencies used directly in the lifespan
    mock_settings_instance = MagicMock()
    mock_settings_class = mocker.patch("luthien_control.main.Settings", return_value=mock_settings_instance)

    # Be explicit with spec for AsyncMock
    mock_http_client_instance = AsyncMock(spec=httpx.AsyncClient)
    # Ensure aclose is also an AsyncMock if needed, though spec should handle it.
    # mock_http_client_instance.aclose = AsyncMock() # Let's hold off on this nested mock for now.

    mock_http_client_class = mocker.patch(
        "luthien_control.main.httpx.AsyncClient", return_value=mock_http_client_instance
    )

    mock_db_engine_instance = AsyncMock()
    mock_create_db_engine = mocker.patch("luthien_control.main.create_db_engine", return_value=mock_db_engine_instance)

    mock_db_session_factory = MagicMock(name="MockDbSessionFactory")
    mocker.patch("luthien_control.main.get_db_session", new=mock_db_session_factory)

    mock_close_db_engine = mocker.patch("luthien_control.main.close_db_engine")

    # We will let the actual DependencyContainer be created with mocked inputs.
    # So, no mock_dependency_container_instance or specific patch for the class itself here.

    # Import app here to ensure mocks are in place before app is fully initialized
    # with the lifespan. Note: TestClient(app) also triggers lifespan.
    from luthien_control.main import DependencyContainer, app  # Import DependencyContainer for isinstance check

    # 2. Trigger lifespan by using TestClient as a context manager
    with TestClient(app) as client:
        # 3. Assertions for startup
        mock_settings_class.assert_called_once()
        mock_http_client_class.assert_called_once()  # Checks that our mock_http_client_instance was created
        mock_create_db_engine.assert_called_once()

        # Check that DependencyContainer was instantiated (implicitly, by checking its effect on app.state)
        assert hasattr(client.app.state, "dependencies")
        assert isinstance(client.app.state.dependencies, DependencyContainer)
        # Verify the real container has our mocked http_client
        assert client.app.state.dependencies.http_client is mock_http_client_instance

    # 4. Assertions for shutdown
    mock_close_db_engine.assert_called_once()


def test_lifespan_startup_db_engine_exception(mocker):
    """Test lifespan startup when create_db_engine raises an exception."""
    mocker.patch("luthien_control.main.Settings", return_value=MagicMock())
    mock_http_client_instance = AsyncMock()
    mocker.patch("luthien_control.main.httpx.AsyncClient", return_value=mock_http_client_instance)

    db_error_message = "DB engine boom!"
    mock_create_db_engine = mocker.patch(
        "luthien_control.main.create_db_engine", side_effect=RuntimeError(db_error_message)
    )

    mock_close_db_engine = mocker.patch("luthien_control.main.close_db_engine")
    mock_dependency_container_class = mocker.patch("luthien_control.main.DependencyContainer")

    from luthien_control.main import app

    with pytest.raises(RuntimeError, match=f"Failed to initialize database: {db_error_message}"):
        with TestClient(app):  # Startup runs here
            pass  # Lifespan should fail before client is fully usable

    mock_create_db_engine.assert_called_once()
    # Ensure http_client.aclose() was called as part of cleanup after DB failure
    mock_http_client_instance.aclose.assert_called_once()
    # DependencyContainer should not have been called
    mock_dependency_container_class.assert_not_called()
    # close_db_engine should not be called as engine creation failed
    mock_close_db_engine.assert_not_called()


def test_lifespan_startup_db_engine_returns_none(mocker):
    """Test lifespan startup when create_db_engine returns None."""
    mocker.patch("luthien_control.main.Settings", return_value=MagicMock())
    mock_http_client_instance = AsyncMock()
    mocker.patch("luthien_control.main.httpx.AsyncClient", return_value=mock_http_client_instance)

    mock_create_db_engine = mocker.patch("luthien_control.main.create_db_engine", return_value=None)

    mock_close_db_engine = mocker.patch("luthien_control.main.close_db_engine")
    mock_dependency_container_class = mocker.patch("luthien_control.main.DependencyContainer")

    from luthien_control.main import app

    with pytest.raises(RuntimeError, match="Failed to initialize database connection engine."):
        with TestClient(app):
            pass

    mock_create_db_engine.assert_called_once()
    mock_http_client_instance.aclose.assert_called_once()
    mock_dependency_container_class.assert_not_called()
    mock_close_db_engine.assert_not_called()


def test_lifespan_startup_dependency_container_exception(mocker):
    """Test lifespan startup when DependencyContainer instantiation fails."""
    mocker.patch("luthien_control.main.Settings", return_value=MagicMock())

    mock_http_client_instance = AsyncMock()
    mocker.patch("luthien_control.main.httpx.AsyncClient", return_value=mock_http_client_instance)

    mock_db_engine_instance = AsyncMock()  # Successfully created engine
    mocker.patch("luthien_control.main.create_db_engine", return_value=mock_db_engine_instance)
    mocker.patch("luthien_control.main.get_db_session", return_value=MagicMock())

    mock_close_db_engine = mocker.patch("luthien_control.main.close_db_engine")

    container_error_message = "Container boom!"
    mock_dependency_container_class = mocker.patch(
        "luthien_control.main.DependencyContainer", side_effect=ValueError(container_error_message)
    )

    from luthien_control.main import app

    with pytest.raises(RuntimeError, match=f"Failed to create Dependency Container: {container_error_message}"):
        with TestClient(app):
            pass

    mock_dependency_container_class.assert_called_once()  # Attempted to create
    mock_http_client_instance.aclose.assert_called_once()  # Cleaned up
    mock_close_db_engine.assert_called_once()  # Cleaned up


# TODO: Add more comprehensive tests for the lifespan function
#       - Mock dependencies (Settings, httpx.AsyncClient, db_engine, DependencyContainer)
#       - Verify resource creation, storage in app.state, and cleanup
#       - Test error handling during startup (e.g., DB connection failure)

# TODO: Add tests for OpenAPI generation
#       - Verify create_custom_openapi is called
#       - Potentially check specific parts of the generated schema
