from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request, status
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import PolicyLoadError
from luthien_control.core.dependencies import (
    get_dependencies,
    get_main_control_policy,
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


# --- Tests for get_main_control_policy (using Container) ---


# Patch load_policy_from_db where it's used inside the dependencies module
@pytest.mark.asyncio
@patch("luthien_control.core.dependencies.load_policy_from_db", new_callable=AsyncMock)
async def test_get_main_control_policy_success(
    mock_load_from_db: AsyncMock,
    mock_container: MagicMock,
):
    """Test successful loading of the main control policy using the dependencies container."""
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
async def test_get_main_control_policy_name_not_configured(
    mock_load_from_db: AsyncMock,
    mock_container: MagicMock,
):
    """Test case where TOP_LEVEL_POLICY_NAME is not set in dependencies container's settings."""
    mock_container.settings.get_top_level_policy_name.return_value = None

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
async def test_get_main_control_policy_load_error(
    mock_load_from_db: AsyncMock,
    mock_container: MagicMock,
):
    """Test handling other PolicyLoadError from load_policy_from_db."""
    policy_name = "test_policy"
    mock_container.settings.get_top_level_policy_name.return_value = policy_name
    load_error = PolicyLoadError(f"Failed loading '{policy_name}'")
    mock_load_from_db.side_effect = load_error

    with pytest.raises(HTTPException) as exc_info:
        await get_main_control_policy(dependencies=mock_container)

    assert exc_info.value.status_code == 500
    assert "Could not load main control policy" in exc_info.value.detail
    assert str(load_error) in exc_info.value.detail
    mock_load_from_db.assert_awaited_once()


@pytest.mark.asyncio
@patch("luthien_control.core.dependencies.load_policy_from_db", new_callable=AsyncMock)
async def test_get_main_control_policy_unexpected_error(
    mock_load_from_db: AsyncMock,
    mock_container: MagicMock,
):
    """Test handling unexpected exceptions from load_policy_from_db."""
    mock_container.settings.get_top_level_policy_name.return_value = "test_policy"
    mock_load_from_db.side_effect = ValueError("Something went wrong")

    with pytest.raises(HTTPException) as exc_info:
        await get_main_control_policy(dependencies=mock_container)

    assert exc_info.value.status_code == 500
    assert "Unexpected issue loading main control policy" in exc_info.value.detail
    mock_load_from_db.assert_awaited_once()
