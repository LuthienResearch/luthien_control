"""Unit tests for core ControlPolicy implementations."""

from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlparse  # Added for host check

import httpx
import pytest
from luthien_control.config.settings import Settings
from luthien_control.control_policy.send_backend_request import SendBackendRequestPolicy
from luthien_control.core.context import TransactionContext

# Mark all tests in this module as unit tests
pytestmark = [pytest.mark.unit, pytest.mark.asyncio]


@pytest.fixture
def mock_settings() -> MagicMock:
    settings = MagicMock(spec=Settings)
    settings.get_backend_url.return_value = "http://mock-backend.test"
    return settings


@pytest.fixture
def mock_http_client() -> MagicMock:
    """Provides a mock httpx.AsyncClient."""
    client = MagicMock(spec=httpx.AsyncClient)
    # Mock the send method to return an async mock response by default
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.aread = AsyncMock(return_value=b"mock body")
    client.send.return_value = mock_response
    return client


@pytest.fixture
def base_context(mock_settings: MagicMock) -> TransactionContext:
    """Provides a base context with a request, relative_path and settings."""
    mock_request = httpx.Request(
        "GET",
        "http://proxy.luthien.local:8000/api/v1/some/path?query=1",
        headers={"X-Original-Header": "original", b"Accept-Encoding": b"gzip"},  # Add accept-encoding
    )
    # Create context *without* settings initially
    context = TransactionContext(
        transaction_id="tx-test-1",
        request=mock_request,
        data={"relative_path": "v1/some/path"},
    )
    # Add settings as an attribute after creation, mimicking how it might be added
    # by an earlier policy or dependency if needed by this policy directly.
    context.settings = mock_settings
    return context


@pytest.fixture
def policy(mock_http_client: MagicMock) -> SendBackendRequestPolicy:
    """Provides an instance of the policy initialized with the mock client."""
    return SendBackendRequestPolicy(http_client=mock_http_client)


async def test_send_request_policy_success(
    policy: SendBackendRequestPolicy, mock_http_client: MagicMock, base_context: TransactionContext
):
    """Test successful request sending, response storage, and raw body reading."""
    # Arrange
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.aread = AsyncMock(return_value=b"Raw response body")
    mock_response.status_code = 200
    mock_response.headers = httpx.Headers({"X-Backend-Header": "backend"})
    mock_response.request = base_context.request
    mock_http_client.send.return_value = mock_response

    # Act
    updated_context = await policy.apply(base_context)

    # Assert
    assert updated_context is base_context
    mock_http_client.send.assert_awaited_once()
    sent_request: httpx.Request = mock_http_client.send.await_args[0][0]

    assert str(sent_request.url) == "http://mock-backend.test/v1/some/path?query=1"
    assert sent_request.method == "GET"
    assert sent_request.headers["X-Original-Header"] == "original"
    assert sent_request.headers["host"] == "mock-backend.test"
    assert sent_request.headers["accept-encoding"] == "identity"  # Verify override
    assert updated_context.response is mock_response
    mock_response.aread.assert_awaited_once()
    assert updated_context.data["raw_backend_response_body"] == b"Raw response body"


async def test_send_request_policy_no_request_in_context(policy: SendBackendRequestPolicy, mock_settings: MagicMock):
    """Test ValueError if context.request is None."""
    empty_context = TransactionContext(transaction_id="tx-empty")
    empty_context.settings = mock_settings  # Add settings attribute

    with pytest.raises(ValueError, match="Cannot send request: context.request is None"):
        await policy.apply(empty_context)


async def test_send_request_policy_http_error(
    policy: SendBackendRequestPolicy, mock_http_client: MagicMock, base_context: TransactionContext
):
    """Test behavior when httpx.send raises an exception."""
    mock_http_client.send.side_effect = httpx.NetworkError("Connection refused")

    with pytest.raises(httpx.NetworkError, match="Connection refused"):
        await policy.apply(base_context)

    mock_http_client.send.assert_awaited_once()
    assert base_context.response is None
    assert "raw_backend_response_body" not in base_context.data


async def test_send_request_policy_body_read_error(
    policy: SendBackendRequestPolicy, mock_http_client: MagicMock, base_context: TransactionContext
):
    """Test behavior when response.aread() raises an exception."""
    # Arrange
    mock_response = MagicMock(spec=httpx.Response)
    read_error = IOError("Failed to read stream")
    mock_response.aread = AsyncMock(side_effect=read_error)
    mock_response.request = base_context.request  # Link for potential logging
    mock_response.status_code = 500  # Add status code even for error case
    mock_http_client.send.return_value = mock_response

    # Act & Assert
    with pytest.raises(IOError, match="Failed to read stream"):
        await policy.apply(base_context)

    # Verify send was called
    mock_http_client.send.assert_awaited_once()
    # Verify aread was called
    mock_response.aread.assert_awaited_once()
    # Verify context.response is None after error
    assert base_context.response is None
    # Ensure raw body was not stored
    assert "raw_backend_response_body" not in base_context.data


async def test_send_request_policy_no_relative_path(
    policy: SendBackendRequestPolicy, mock_http_client: MagicMock, mock_settings: MagicMock
):
    """Test ValueError if relative_path is not in context.data."""
    context_no_path = TransactionContext(
        transaction_id="tx-no-path",
        request=httpx.Request("GET", "http://proxy.luthien.local:8000/api/some/path"),
        data={},  # Missing relative_path
    )
    context_no_path.settings = mock_settings  # Add settings attribute

    with pytest.raises(ValueError, match="Cannot send request: relative_path not found"):
        await policy.apply(context_no_path)

    mock_http_client.send.assert_not_called()


async def test_send_request_invalid_backend_url(
    mock_settings, policy: SendBackendRequestPolicy, base_context: TransactionContext
):
    """Test ValueError if backend_url from settings is invalid."""
    mock_settings.get_backend_url.return_value = "invalid-url-no-scheme"
    # Ensure the context being passed has the mocked settings
    base_context.settings = mock_settings

    # The policy reads context.settings directly now
    with pytest.raises(ValueError, match="Could not parse scheme or netloc from BACKEND_URL"):
        await policy.apply(base_context)

    policy.http_client.send.assert_not_called()
