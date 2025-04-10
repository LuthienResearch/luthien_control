from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException, Request
from luthien_control.control_policy.initialize_context import InitializeContextPolicy
from luthien_control.core.response_builder.default_builder import DefaultResponseBuilder
from luthien_control.db.crud import get_api_key_by_value
from luthien_control.dependencies import (
    get_http_client,
    get_initial_context_policy,
    get_response_builder,
)
from starlette.datastructures import State


@pytest.fixture
def mock_api_key_crud():
    """Fixture to mock the get_api_key_by_value CRUD function."""
    return AsyncMock(spec=get_api_key_by_value)


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
