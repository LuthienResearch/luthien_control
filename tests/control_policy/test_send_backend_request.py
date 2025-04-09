"""Unit tests for core ControlPolicy implementations."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from luthien_control.control_policy.send_backend_request import SendBackendRequestPolicy
from luthien_control.core.context import TransactionContext

# Mark all tests in this module as async tests
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_http_client() -> MagicMock:
    """Provides a mock httpx.AsyncClient."""
    client = MagicMock(spec=httpx.AsyncClient)
    # Mock the async send method
    client.send = AsyncMock()
    return client


@pytest.fixture
def policy(mock_http_client: MagicMock) -> SendBackendRequestPolicy:
    """Provides an instance of the policy with a mock client."""
    return SendBackendRequestPolicy(http_client=mock_http_client)


@pytest.fixture
def base_context() -> TransactionContext:
    """Provides a base TransactionContext."""
    return TransactionContext(transaction_id="tx-test-1")


async def test_send_request_policy_success(
    policy: SendBackendRequestPolicy, mock_http_client: MagicMock, base_context: TransactionContext
):
    """Test successful request sending, response storage, and raw body reading."""
    # Arrange
    mock_request = httpx.Request("GET", "http://mock-backend.test/path")
    # Mock the response object and its async methods
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.aread = AsyncMock(return_value=b"Raw response body")
    # Ensure necessary attributes exist on the mock response for context storage
    mock_response.status_code = 200
    mock_response.headers = httpx.Headers()
    mock_response.request = mock_request

    base_context.request = mock_request
    mock_http_client.send.return_value = mock_response

    # Act
    updated_context = await policy.apply(base_context)

    # Assert
    mock_http_client.send.assert_awaited_once_with(mock_request)
    mock_response.aread.assert_awaited_once()  # Verify body was read
    assert updated_context is base_context  # Should modify in place
    # Check that the *original* response object is stored
    assert updated_context.response is mock_response
    # Check that the raw body is stored in context.data
    assert updated_context.data.get("raw_backend_response_body") == b"Raw response body"


async def test_send_request_policy_no_request_in_context(
    policy: SendBackendRequestPolicy, mock_http_client: MagicMock, base_context: TransactionContext
):
    """Test behavior when context.request is None."""
    # Arrange
    base_context.request = None

    # Act & Assert
    with pytest.raises(ValueError, match="Cannot send request: context.request is None"):
        await policy.apply(base_context)

    mock_http_client.send.assert_not_awaited()
    assert "raw_backend_response_body" not in base_context.data  # Ensure data not polluted


async def test_send_request_policy_http_error(
    policy: SendBackendRequestPolicy, mock_http_client: MagicMock, base_context: TransactionContext
):
    """Test behavior when httpx.send raises an exception."""
    # Arrange
    mock_request = httpx.Request("GET", "http://mock-backend.test/path")
    base_context.request = mock_request
    mock_http_client.send.side_effect = httpx.NetworkError("Connection refused")

    # Act & Assert
    with pytest.raises(httpx.NetworkError, match="Connection refused"):
        await policy.apply(base_context)

    mock_http_client.send.assert_awaited_once_with(mock_request)
    assert base_context.response is None  # Response should not be set on error
    assert "raw_backend_response_body" not in base_context.data  # Ensure data not polluted


# TODO: Add test for case where response.aread() fails?
