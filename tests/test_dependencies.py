from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import HTTPException, Request
from luthien_control.config.settings import Settings
from luthien_control.control_policy.initialize_context import InitializeContextPolicy
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.core.response_builder.default_builder import DefaultResponseBuilder
from luthien_control.db.sqlmodel_crud import PolicyLoadError, get_api_key_by_value
from luthien_control.dependencies import (
    get_http_client,
    get_initial_context_policy,
    get_main_control_policy,
    get_response_builder,
)
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import State

# --- Tests for get_http_client ---


@pytest.fixture
def mock_request_with_state() -> Request:
    """Creates a mock Request object with a mock app.state."""
    request = AsyncMock(spec=Request)
    request.app = AsyncMock()
    request.app.state = State()
    return request


def test_get_http_client_success(mock_request_with_state):
    """Test successfully retrieving the http_client from request state."""
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_request_with_state.app.state.http_client = mock_client

    client = get_http_client(mock_request_with_state)

    assert client is mock_client


def test_get_http_client_not_found(mock_request_with_state):
    """Test raising HTTPException when http_client is not in request state."""
    # Ensure the client is not set
    assert not hasattr(mock_request_with_state.app.state, "http_client")

    with pytest.raises(HTTPException) as exc_info:
        get_http_client(mock_request_with_state)

    assert exc_info.value.status_code == 500
    assert "HTTP client not available" in exc_info.value.detail


# --- Tests for Simple Dependency Providers ---


def test_get_initial_context_policy():
    """Test that get_initial_context_policy returns the correct policy instance."""
    policy = get_initial_context_policy()
    assert isinstance(policy, InitializeContextPolicy)


def test_get_response_builder():
    """Test that get_response_builder returns the correct builder instance."""
    builder = get_response_builder()
    assert isinstance(builder, DefaultResponseBuilder)


# --- Tests for get_main_control_policy ---


@pytest.fixture
def mock_settings() -> MagicMock:
    """Fixture for a mocked Settings object."""
    settings = MagicMock(spec=Settings)
    settings.get_top_level_policy_name.return_value = "test-root-policy"
    return settings


@pytest.fixture
def mock_http_client_dep() -> AsyncMock:
    """Fixture for a mocked httpx.AsyncClient (dependency)."""
    return AsyncMock(spec=httpx.AsyncClient)


# Note: We patch 'luthien_control.dependencies.load_policy_from_db' because
# that's the reference used *within* the get_main_control_policy function.
@pytest.mark.asyncio
@patch("luthien_control.dependencies.load_policy_from_db", new_callable=AsyncMock)
async def test_get_main_control_policy_success(
    mock_load_from_db: AsyncMock,
    mock_settings: MagicMock,
    mock_http_client_dep: AsyncMock,
):
    """Test successful loading of the main control policy."""
    mock_policy = AsyncMock(spec=ControlPolicy)
    mock_load_from_db.return_value = mock_policy
    policy_name = "test-root-policy"

    # We need to mock the session that get_main_control_policy receives via Depends(get_db)
    # Since we are calling the function directly, we need to pass the dependencies manually.
    # The session dependency needs to be handled.
    mock_session = AsyncMock(spec=AsyncSession)

    result_policy = await get_main_control_policy(
        settings=mock_settings,
        http_client=mock_http_client_dep,
        session=mock_session,  # Pass the mocked session explicitly
    )

    # Assertions
    mock_settings.get_top_level_policy_name.assert_called_once()
    mock_load_from_db.assert_awaited_once_with(
        name=policy_name,
        settings=mock_settings,
        http_client=mock_http_client_dep,
        api_key_lookup=get_api_key_by_value,  # Check that the correct function reference is passed
        session=mock_session,  # Add session to the expected call args
    )
    assert result_policy is mock_policy


@pytest.mark.asyncio
@patch("luthien_control.dependencies.load_policy_from_db", new_callable=AsyncMock)
async def test_get_main_control_policy_name_not_configured(
    mock_load_from_db: AsyncMock,
    mock_settings: MagicMock,
    mock_http_client_dep: AsyncMock,
):
    """Test case where TOP_LEVEL_POLICY_NAME is not set in settings."""
    mock_settings.get_top_level_policy_name.return_value = None

    with pytest.raises(HTTPException) as exc_info:
        await get_main_control_policy(
            settings=mock_settings,
            http_client=mock_http_client_dep,
        )

    assert exc_info.value.status_code == 500
    assert "Control policy name not configured" in exc_info.value.detail
    mock_load_from_db.assert_not_awaited()


@pytest.mark.asyncio
@patch("luthien_control.dependencies.load_policy_from_db", new_callable=AsyncMock)
async def test_get_main_control_policy_not_found_error(
    mock_load_from_db: AsyncMock,
    mock_settings: MagicMock,
    mock_http_client_dep: AsyncMock,
):
    """Test handling when load_policy_from_db raises PolicyLoadError for not found."""
    policy_name = "test-root-policy"
    # crud.load_policy_from_db raises PolicyLoadError for not found cases
    mock_load_from_db.side_effect = PolicyLoadError(
        f"Active policy configuration named '{policy_name}' not found in database."
    )

    with pytest.raises(HTTPException) as exc_info:
        await get_main_control_policy(
            settings=mock_settings,
            http_client=mock_http_client_dep,
        )

    assert exc_info.value.status_code == 500
    assert "Could not load main control policy" in exc_info.value.detail
    # Check for the specific message raised by load_policy_from_db within the overall error detail
    assert f"Active policy configuration named '{policy_name}' not found" in exc_info.value.detail
    mock_load_from_db.assert_awaited_once()


@pytest.mark.asyncio
@patch("luthien_control.dependencies.load_policy_from_db", new_callable=AsyncMock)
async def test_get_main_control_policy_load_error(
    mock_load_from_db: AsyncMock,
    mock_settings: MagicMock,
    mock_http_client_dep: AsyncMock,
):
    """Test handling PolicyLoadError from load_policy_from_db."""
    policy_name = "test-root-policy"
    mock_load_from_db.side_effect = PolicyLoadError(f"Failed loading '{policy_name}'")

    with pytest.raises(HTTPException) as exc_info:
        await get_main_control_policy(
            settings=mock_settings,
            http_client=mock_http_client_dep,
        )

    assert exc_info.value.status_code == 500
    assert "Could not load main control policy" in exc_info.value.detail
    assert f"Failed loading '{policy_name}'" in exc_info.value.detail
    mock_load_from_db.assert_awaited_once()


@pytest.mark.asyncio
@patch("luthien_control.dependencies.load_policy_from_db", new_callable=AsyncMock)
async def test_get_main_control_policy_unexpected_error(
    mock_load_from_db: AsyncMock,
    mock_settings: MagicMock,
    mock_http_client_dep: AsyncMock,
):
    """Test handling unexpected exceptions from load_policy_from_db."""
    mock_load_from_db.side_effect = ValueError("Something went wrong")

    with pytest.raises(HTTPException) as exc_info:
        await get_main_control_policy(
            settings=mock_settings,
            http_client=mock_http_client_dep,
        )

    assert exc_info.value.status_code == 500
    assert "Unexpected issue loading main control policy" in exc_info.value.detail
    mock_load_from_db.assert_awaited_once()
