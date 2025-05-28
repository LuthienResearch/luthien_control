from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
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


def test_lifespan_success_path(mocker, mock_container: MagicMock):
    """Test the successful startup and shutdown sequence of the app lifespan using the new strategy."""
    # 1. Mock dependencies directly used by lifespan, or global ones for shutdown.
    mock_settings_instance = MagicMock()
    mocker.patch("luthien_control.main.Settings", return_value=mock_settings_instance)

    mock_initialize_dependencies = mocker.patch(
        "luthien_control.main.initialize_app_dependencies",
        new_callable=AsyncMock,  # Ensures the mock itself is an awaitable coroutine function
        return_value=mock_container,  # The coroutine function will return mock_container when awaited
    )

    mock_close_db_engine = mocker.patch("luthien_control.main.close_db_engine")

    # Import app here to ensure mocks are in place.
    from luthien_control.main import app

    # 2. Trigger lifespan by using TestClient as a context manager
    with TestClient(app) as client:
        # 3. Assertions for startup
        # Settings should be loaded once by lifespan

        # Assert that our helper was called with the settings instance
        mock_initialize_dependencies.assert_awaited_once_with(mock_settings_instance)

        # Check that DependencyContainer from the helper was stored in app.state
        current_app = cast(FastAPI, client.app)
        assert hasattr(current_app.state, "dependencies")
        assert current_app.state.dependencies is mock_container
        # We can also check that the http_client on our mock_container is the one from its own fixture setup.
        # This is implicitly tested if mock_container is correctly composed.
        assert current_app.state.dependencies.http_client is mock_container.http_client

    # 4. Assertions for shutdown
    # Check that the http_client on our mock_container had its aclose called
    mock_container.http_client.aclose.assert_awaited_once()  # mock_container.http_client is an AsyncMock

    mock_close_db_engine.assert_awaited_once()


def test_lifespan_startup_db_engine_exception(mocker):
    """Test lifespan startup when _initialize_app_dependencies fails due to a simulated DB engine issue."""
    mock_settings_instance = MagicMock()
    mocker.patch("luthien_control.main.Settings", return_value=mock_settings_instance)

    db_error_message = "DB engine boom during init!"
    # Patch _initialize_app_dependencies to raise an exception, as if DB creation failed within it.
    # It's an async function, so its mock should reflect that if using side_effect for exceptions.
    mock_initialize_dependencies = mocker.patch(
        "luthien_control.main.initialize_app_dependencies",
        new_callable=AsyncMock,
        side_effect=RuntimeError(db_error_message),  # This error will be raised when awaited
    )

    # Lifespan should call close_db_engine in its exception handler.
    mock_close_db_engine = mocker.patch("luthien_control.main.close_db_engine")

    from luthien_control.main import app

    # The lifespan will catch the db_error_message and re-raise its own wrapping error.
    expected_wrapper_error_match = (
        f"Application startup failed due to dependency initialization error: {db_error_message}"
    )

    with pytest.raises(RuntimeError, match=expected_wrapper_error_match):
        with TestClient(app):  # Startup runs here and should fail
            pass

    # Assert that _initialize_app_dependencies was called (attempted)
    mock_initialize_dependencies.assert_awaited_once_with(mock_settings_instance)

    # Assert that close_db_engine was called by lifespan's exception handler
    mock_close_db_engine.assert_awaited_once()


def test_lifespan_startup_db_engine_returns_none(mocker):
    """Test lifespan startup when _initialize_app_dependencies fails as if create_db_engine returned None."""
    mock_settings_instance = MagicMock()
    mocker.patch("luthien_control.main.Settings", return_value=mock_settings_instance)

    # This is the specific error _initialize_app_dependencies raises if create_db_engine returns None.
    internal_error_message = "Failed to initialize database connection engine for DependencyContainer."
    mock_initialize_dependencies = mocker.patch(
        "luthien_control.main.initialize_app_dependencies",
        new_callable=AsyncMock,
        side_effect=RuntimeError(internal_error_message),
    )

    mock_close_db_engine = mocker.patch("luthien_control.main.close_db_engine")

    from luthien_control.main import app

    expected_wrapper_error_match = (
        f"Application startup failed due to dependency initialization error: {internal_error_message}"
    )

    with pytest.raises(RuntimeError, match=expected_wrapper_error_match):
        with TestClient(app):
            pass

    mock_initialize_dependencies.assert_awaited_once_with(mock_settings_instance)
    mock_close_db_engine.assert_awaited_once()


def test_lifespan_startup_dependency_container_exception(mocker):
    """Test lifespan startup when _initialize_app_dependencies fails due to DependencyContainer instantiation issue."""
    mock_settings_instance = MagicMock()
    mocker.patch("luthien_control.main.Settings", return_value=mock_settings_instance)

    container_error_message = "Container boom!"
    # This is the specific error _initialize_app_dependencies raises if DependencyContainer init fails.
    internal_error_message = f"Failed to create Dependency Container instance: {container_error_message}"

    # We need to simulate that _initialize_app_dependencies itself raises this error
    mock_initialize_dependencies = mocker.patch(
        "luthien_control.main.initialize_app_dependencies",
        new_callable=AsyncMock,
        side_effect=RuntimeError(internal_error_message),  # Simulates the helper failing at container creation
    )

    # Lifespan should call close_db_engine in its exception handler
    mock_close_db_engine = mocker.patch("luthien_control.main.close_db_engine")

    from luthien_control.main import app

    # Lifespan will wrap this internal_error_message
    expected_wrapper_error_match = (
        f"Application startup failed due to dependency initialization error: {internal_error_message}"
    )

    with pytest.raises(RuntimeError, match=expected_wrapper_error_match):
        with TestClient(app):
            pass

    # Assert that _initialize_app_dependencies was called (attempted)
    mock_initialize_dependencies.assert_awaited_once_with(mock_settings_instance)

    # Assert that close_db_engine was called by lifespan's exception handler
    mock_close_db_engine.assert_awaited_once()
