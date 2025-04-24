from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request, status
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import PolicyLoadError
from luthien_control.dependencies import (
    get_async_db_session_from_dependencies,
    get_dependencies,
    get_http_client,
    get_main_control_policy,
    get_settings,
)
from starlette.datastructures import State

# --- Fixtures (reusing mocks from conftest via dependency injection) ---

# No need for local mock_settings, mock_http_client etc., use ones from conftest


@pytest.fixture
def mock_request_with_state() -> Request:
    """Creates a mock Request object with a mock app.state."""
    request = AsyncMock(spec=Request)
    request.app = AsyncMock()
    request.app.state = State()
    return request


# --- Tests for get_container ---


def test_get_dependencies_success(mock_request_with_state, mock_dependencies):
    """Test successfully retrieving the DependencyContainer from request state."""
    mock_request_with_state.app.state.dependencies = mock_dependencies
    dependencies = get_dependencies(mock_request_with_state)
    assert dependencies is mock_dependencies


def test_get_dependencies_not_found(mock_request_with_state):
    """Test raising HTTPException when dependencies are not in request state."""
    assert not hasattr(mock_request_with_state.app.state, "dependencies")
    with pytest.raises(HTTPException) as exc_info:
        get_dependencies(mock_request_with_state)
    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Application dependencies not initialized" in exc_info.value.detail


# --- Tests for Simple Dependency Providers (using Container) ---


def test_get_settings(mock_dependencies):
    """Test getting settings from the dependencies container."""
    settings = get_settings(mock_dependencies)
    assert settings is mock_dependencies.settings


def test_get_http_client(mock_dependencies):
    """Test getting http_client from the dependencies container."""
    client = get_http_client(mock_dependencies)
    assert client is mock_dependencies.http_client


@pytest.mark.asyncio
async def test_get_async_db_session_from_dependencies_success(mock_dependencies, mock_db_session):
    """Test getting a db session successfully from the dependencies container factory."""
    session_generator = get_async_db_session_from_dependencies(mock_dependencies)
    async with session_generator as session:
        assert session is mock_db_session
    # Check factory was called
    mock_dependencies.db_session_factory.assert_called_once()
    # Check context manager methods were called
    mock_dependencies.db_session_factory.return_value.__aenter__.assert_awaited_once()
    mock_dependencies.db_session_factory.return_value.__aexit__.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_async_db_session_from_container_factory_missing(mock_dependencies):
    """Test error when db_session_factory is None in dependencies container."""
    mock_dependencies.db_session_factory = None
    session_generator = get_async_db_session_from_dependencies(mock_dependencies)
    with pytest.raises(HTTPException) as exc_info:
        async with session_generator:
            pass  # pragma: no cover
    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "session factory not available" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_async_db_session_from_container_factory_raises_runtime(mock_dependencies):
    """Test handling RuntimeError during session creation from factory."""
    mock_dependencies.db_session_factory.return_value.__aenter__.side_effect = RuntimeError("DB init failed")
    session_generator = get_async_db_session_from_dependencies(mock_dependencies)
    with pytest.raises(HTTPException) as exc_info:
        async with session_generator:
            pass  # pragma: no cover
    assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "Database not available" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_async_db_session_from_container_factory_raises_other(mock_dependencies):
    """Test handling other exceptions during session creation from factory."""
    mock_dependencies.db_session_factory.return_value.__aenter__.side_effect = ValueError("Bad config")
    session_generator = get_async_db_session_from_dependencies(mock_dependencies)
    with pytest.raises(HTTPException) as exc_info:
        async with session_generator:
            pass  # pragma: no cover
    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Internal server error" in exc_info.value.detail


# --- Tests for get_main_control_policy (using Container) ---


# Patch load_policy_from_db where it's used inside the dependencies module
@pytest.mark.asyncio
@patch("luthien_control.dependencies.load_policy_from_db", new_callable=AsyncMock)
async def test_get_main_control_policy_success(
    mock_load_from_db: AsyncMock,
    mock_dependencies: MagicMock,
):
    """Test successful loading of the main control policy using the dependencies container."""
    mock_policy = AsyncMock(spec=ControlPolicy)
    mock_load_from_db.return_value = mock_policy
    policy_name = "test_policy"  # From mock_dependencies.settings
    mock_dependencies.settings.get_top_level_policy_name.return_value = policy_name

    # Call the dependency function, passing the mocked dependencies
    result_policy = await get_main_control_policy(dependencies=mock_dependencies)

    # Assertions
    mock_dependencies.settings.get_top_level_policy_name.assert_called_once()
    # Check session factory was called to get a session
    mock_dependencies.db_session_factory.assert_called_once()
    mock_session = mock_dependencies.mock_session  # Get the mock session via the helper attribute
    # Check load_policy_from_db was awaited correctly with dependencies components
    mock_load_from_db.assert_awaited_once_with(
        name=policy_name,
        settings=mock_dependencies.settings,
        http_client=mock_dependencies.http_client,
        session=mock_session,  # Ensure the session from the factory was passed
    )
    assert result_policy is mock_policy


@pytest.mark.asyncio
@patch("luthien_control.dependencies.load_policy_from_db", new_callable=AsyncMock)
async def test_get_main_control_policy_name_not_configured(
    mock_load_from_db: AsyncMock,
    mock_dependencies: MagicMock,
):
    """Test case where TOP_LEVEL_POLICY_NAME is not set in dependencies container's settings."""
    mock_dependencies.settings.get_top_level_policy_name.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await get_main_control_policy(dependencies=mock_dependencies)

    assert exc_info.value.status_code == 500
    assert "Control policy name not configured" in exc_info.value.detail
    mock_load_from_db.assert_not_awaited()


@pytest.mark.asyncio
@patch("luthien_control.dependencies.load_policy_from_db", new_callable=AsyncMock)
async def test_get_main_control_policy_not_found_error(
    mock_load_from_db: AsyncMock,
    mock_dependencies: MagicMock,
):
    """Test handling PolicyLoadError(not found) from load_policy_from_db."""
    policy_name = "test_policy"
    mock_dependencies.settings.get_top_level_policy_name.return_value = policy_name
    mock_load_from_db.return_value = None  # Simulate not found

    with pytest.raises(HTTPException) as exc_info:
        await get_main_control_policy(dependencies=mock_dependencies)

    assert exc_info.value.status_code == 500
    assert f"Main control policy '{policy_name}' not found or inactive" in exc_info.value.detail
    mock_load_from_db.assert_awaited_once()


@pytest.mark.asyncio
@patch("luthien_control.dependencies.load_policy_from_db", new_callable=AsyncMock)
async def test_get_main_control_policy_load_error(
    mock_load_from_db: AsyncMock,
    mock_dependencies: MagicMock,
):
    """Test handling other PolicyLoadError from load_policy_from_db."""
    policy_name = "test_policy"
    mock_dependencies.settings.get_top_level_policy_name.return_value = policy_name
    load_error = PolicyLoadError(f"Failed loading '{policy_name}'")
    mock_load_from_db.side_effect = load_error

    with pytest.raises(HTTPException) as exc_info:
        await get_main_control_policy(dependencies=mock_dependencies)

    assert exc_info.value.status_code == 500
    assert "Could not load main control policy" in exc_info.value.detail
    assert str(load_error) in exc_info.value.detail
    mock_load_from_db.assert_awaited_once()


@pytest.mark.asyncio
@patch("luthien_control.dependencies.load_policy_from_db", new_callable=AsyncMock)
async def test_get_main_control_policy_session_factory_error(
    mock_load_from_db: AsyncMock,
    mock_dependencies: MagicMock,
):
    """Test handling error raised by the session factory context manager itself."""
    mock_dependencies.settings.get_top_level_policy_name.return_value = "test_policy"
    # Simulate error when entering the session context
    factory_error = HTTPException(status_code=503, detail="DB Boom")
    mock_dependencies.db_session_factory.return_value.__aenter__.side_effect = factory_error

    with pytest.raises(HTTPException) as exc_info:
        await get_main_control_policy(dependencies=mock_dependencies)

    # The HTTPException from the session context should propagate
    assert exc_info.value is factory_error
    mock_load_from_db.assert_not_awaited()  # Should fail before loading policy


@pytest.mark.asyncio
@patch("luthien_control.dependencies.load_policy_from_db", new_callable=AsyncMock)
async def test_get_main_control_policy_unexpected_error(
    mock_load_from_db: AsyncMock,
    mock_dependencies: MagicMock,
):
    """Test handling unexpected exceptions from load_policy_from_db."""
    mock_dependencies.settings.get_top_level_policy_name.return_value = "test_policy"
    mock_load_from_db.side_effect = ValueError("Something went wrong")

    with pytest.raises(HTTPException) as exc_info:
        await get_main_control_policy(dependencies=mock_dependencies)

    assert exc_info.value.status_code == 500
    assert "Unexpected issue loading main control policy" in exc_info.value.detail
    mock_load_from_db.assert_awaited_once()
