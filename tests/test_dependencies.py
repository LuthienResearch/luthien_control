import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request, status
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import PolicyLoadError
from luthien_control.core.dependencies import (
    get_db_session,
    get_dependencies,
    get_main_control_policy,
    initialize_app_dependencies,
)
from luthien_control.core.dependency_container import DependencyContainer
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


def test_get_dependencies_success(mock_request_with_state, mock_container):
    """Test successfully retrieving the DependencyContainer from request state."""
    mock_request_with_state.app.state.dependencies = mock_container
    dependencies = get_dependencies(mock_request_with_state)
    assert dependencies is mock_container


def test_get_dependencies_not_found(mock_request_with_state):
    """Test raising HTTPException when dependencies are not in request state."""
    assert not hasattr(mock_request_with_state.app.state, "dependencies")
    with pytest.raises(HTTPException) as exc_info:
        get_dependencies(mock_request_with_state)
    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Application dependencies not initialized" in exc_info.value.detail


# --- Tests for get_db_session ---


@pytest.mark.asyncio
async def test_get_db_session_success(mock_container):
    """Test successful database session retrieval."""
    mock_session = AsyncMock()

    # Mock the async context manager that get_db_session expects
    @contextlib.asynccontextmanager
    async def mock_session_factory():
        yield mock_session

    mock_container.db_session_factory = mock_session_factory

    # Use the async generator properly
    async_gen = get_db_session(dependencies=mock_container)
    session = await async_gen.__anext__()
    assert session is mock_session

    # Clean up the generator
    try:
        await async_gen.__anext__()
    except StopAsyncIteration:
        pass


@pytest.mark.asyncio
async def test_get_db_session_no_factory(mock_container):
    """Test HTTPException when session factory is None."""
    mock_container.db_session_factory = None

    async_gen = get_db_session(dependencies=mock_container)

    with pytest.raises(HTTPException) as exc_info:
        await async_gen.__anext__()

    assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert "Database session factory not available" in exc_info.value.detail


@pytest.mark.asyncio
async def test_get_db_session_exception_handling(mock_container):
    """Test that exceptions during session usage trigger rollback."""
    mock_session = AsyncMock()

    # Mock the async context manager that get_db_session expects
    @contextlib.asynccontextmanager
    async def mock_session_factory():
        yield mock_session

    mock_container.db_session_factory = mock_session_factory

    async_gen = get_db_session(dependencies=mock_container)
    _ = await async_gen.__anext__()

    # Simulate an exception and trigger the rollback
    try:
        await async_gen.athrow(ValueError("Test exception"))
    except ValueError:
        pass

    # Verify rollback was called
    mock_session.rollback.assert_awaited_once()


# --- Tests for get_main_control_policy (using Container) ---


@pytest.mark.asyncio
@patch("luthien_control.core.dependencies.load_policy_from_file")
async def test_get_main_control_policy_from_file(
    mock_load_from_file: MagicMock,
    mock_container: MagicMock,
):
    """Test loading control policy from file when filepath is provided."""
    filepath = "/path/to/policy.json"
    mock_container.settings.get_policy_filepath.return_value = filepath
    mock_policy = MagicMock(spec=ControlPolicy)
    mock_load_from_file.return_value = mock_policy

    result_policy = await get_main_control_policy(dependencies=mock_container)

    mock_load_from_file.assert_called_once_with(filepath)
    assert result_policy is mock_policy


@pytest.mark.asyncio
@patch("luthien_control.core.dependencies.load_policy_from_db", new_callable=AsyncMock)
async def test_get_main_control_policy_success(
    mock_load_from_db: AsyncMock,
    mock_container: MagicMock,
):
    """Test successful loading of the main control policy using the dependencies container."""
    mock_container.settings.get_policy_filepath.return_value = None
    mock_policy = AsyncMock(spec=ControlPolicy)
    mock_load_from_db.return_value = mock_policy
    policy_name = "test_policy"  # From mock_container.settings
    mock_container.settings.get_top_level_policy_name.return_value = policy_name

    # Call the dependency function, passing the mocked container
    result_policy = await get_main_control_policy(dependencies=mock_container)

    # Assertions
    mock_container.settings.get_top_level_policy_name.assert_called_once()
    # Check load_policy_from_db was awaited correctly with the container
    mock_load_from_db.assert_awaited_once_with(
        name=policy_name,
        container=mock_container,  # Check container is passed
    )
    assert result_policy is mock_policy


@pytest.mark.asyncio
@patch("luthien_control.core.dependencies.load_policy_from_db", new_callable=AsyncMock)
@pytest.mark.parametrize("policy_name", [None, ""])
async def test_get_main_control_policy_name_not_configured(
    mock_load_from_db: AsyncMock,
    mock_container: MagicMock,
    policy_name,
):
    """Test case where TOP_LEVEL_POLICY_NAME is not configured (None or empty string)."""
    mock_container.settings.get_policy_filepath.return_value = None
    mock_container.settings.get_top_level_policy_name.return_value = policy_name

    with pytest.raises(HTTPException) as exc_info:
        await get_main_control_policy(dependencies=mock_container)

    assert exc_info.value.status_code == 500
    assert "Control policy name not configured" in exc_info.value.detail
    mock_load_from_db.assert_not_awaited()


@pytest.mark.asyncio
@patch("luthien_control.core.dependencies.load_policy_from_db", new_callable=AsyncMock)
async def test_get_main_control_policy_not_found_error(
    mock_load_from_db: AsyncMock,
    mock_container: MagicMock,
):
    """Test handling PolicyLoadError(not found) from load_policy_from_db."""
    mock_container.settings.get_policy_filepath.return_value = None
    policy_name = "test_policy"
    mock_container.settings.get_top_level_policy_name.return_value = policy_name
    mock_load_from_db.return_value = None  # Simulate not found

    with pytest.raises(HTTPException) as exc_info:
        await get_main_control_policy(dependencies=mock_container)

    assert exc_info.value.status_code == 500
    assert f"Main control policy '{policy_name}' not found or inactive" in exc_info.value.detail
    mock_load_from_db.assert_awaited_once()


@pytest.mark.asyncio
@patch("luthien_control.core.dependencies.load_policy_from_db", new_callable=AsyncMock)
@pytest.mark.parametrize(
    "exception,expected_detail",
    [
        (PolicyLoadError("Failed loading 'test_policy'"), "Could not load main control policy"),
        (HTTPException(status_code=503, detail="Service unavailable"), None),  # Re-raised as-is
        (ValueError("Something went wrong"), "Unexpected issue loading main control policy"),
    ],
)
async def test_get_main_control_policy_exception_handling(
    mock_load_from_db: AsyncMock,
    mock_container: MagicMock,
    exception,
    expected_detail,
):
    """Test handling various exceptions from load_policy_from_db."""
    mock_container.settings.get_policy_filepath.return_value = None
    mock_container.settings.get_top_level_policy_name.return_value = "test_policy"
    mock_load_from_db.side_effect = exception

    with pytest.raises(HTTPException) as exc_info:
        await get_main_control_policy(dependencies=mock_container)

    if isinstance(exception, HTTPException):
        # HTTPException should be re-raised as-is
        assert exc_info.value is exception
    else:
        assert exc_info.value.status_code == 500
        assert expected_detail in exc_info.value.detail
        if isinstance(exception, PolicyLoadError):
            assert str(exception) in exc_info.value.detail

    mock_load_from_db.assert_awaited_once()


# --- Tests for initialize_app_dependencies ---


@pytest.mark.asyncio
@patch("luthien_control.core.dependencies.create_db_engine", new_callable=AsyncMock)
@patch("luthien_control.core.dependencies.httpx.AsyncClient")
@patch("luthien_control.core.dependencies.db_get_session")
async def test_initialize_app_dependencies_success(
    mock_db_get_session: MagicMock,
    mock_http_client_class: MagicMock,
    mock_create_db_engine: AsyncMock,
    mock_settings: MagicMock,
):
    """Test successful initialization of app dependencies."""
    mock_http_client = AsyncMock()
    mock_http_client_class.return_value = mock_http_client
    mock_db_engine = AsyncMock()
    mock_create_db_engine.return_value = mock_db_engine

    result = await initialize_app_dependencies(mock_settings)

    assert isinstance(result, DependencyContainer)
    assert result.settings is mock_settings
    assert result.http_client is mock_http_client
    assert result.db_session_factory is mock_db_get_session

    mock_create_db_engine.assert_awaited_once()


@pytest.mark.asyncio
@patch("luthien_control.core.dependencies.create_db_engine", new_callable=AsyncMock)
@patch("luthien_control.core.dependencies.httpx.AsyncClient")
@patch("luthien_control.core.dependencies.db_get_session")
@patch("luthien_control.core.dependencies.DependencyContainer")
@pytest.mark.parametrize(
    "failing_mock,exception,expected_error",
    [
        (
            "create_db_engine",
            Exception("Database connection failed"),
            "Failed to initialize database for DependencyContainer",
        ),
        (
            "DependencyContainer",
            Exception("Container creation failed"),
            "Failed to create Dependency Container instance",
        ),
    ],
)
async def test_initialize_app_dependencies_failure_scenarios(
    mock_container_class: MagicMock,
    mock_db_get_session: MagicMock,
    mock_http_client_class: MagicMock,
    mock_create_db_engine: AsyncMock,
    mock_settings: MagicMock,
    failing_mock: str,
    exception: Exception,
    expected_error: str,
):
    """Test handling various initialization failures with proper cleanup."""
    mock_http_client = AsyncMock()
    mock_http_client_class.return_value = mock_http_client
    mock_db_engine = AsyncMock()
    mock_create_db_engine.return_value = mock_db_engine

    # Configure the failing mock
    if failing_mock == "create_db_engine":
        mock_create_db_engine.side_effect = exception
    elif failing_mock == "DependencyContainer":
        mock_container_class.side_effect = exception

    with pytest.raises(RuntimeError, match=expected_error):
        await initialize_app_dependencies(mock_settings)

    # Verify cleanup was called
    mock_http_client.aclose.assert_awaited_once()
