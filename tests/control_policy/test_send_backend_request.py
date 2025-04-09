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
    client.send = AsyncMock()  # Mock the async send method
    return client


@pytest.fixture
def base_context() -> TransactionContext:
    """Provides a base TransactionContext."""
    return TransactionContext(transaction_id="tx-test-1")


@pytest.fixture
def policy(mock_http_client: MagicMock) -> SendBackendRequestPolicy:
    """Provides an instance of SendBackendRequestPolicy with mocks."""
    return SendBackendRequestPolicy(http_client=mock_http_client)


async def test_send_request_policy_success(
    policy: SendBackendRequestPolicy, mock_http_client: MagicMock, base_context: TransactionContext
):
    """Test successful request sending and response storage."""
    # Arrange
    mock_request = httpx.Request("GET", "http://mock-backend.test/path")
    mock_response = httpx.Response(200, request=mock_request, content=b"Success")
    base_context.request = mock_request
    mock_http_client.send.return_value = mock_response

    # Act
    updated_context = await policy.apply(base_context)

    # Assert
    mock_http_client.send.assert_awaited_once_with(mock_request)
    assert updated_context is base_context  # Should modify in place
    assert updated_context.response is mock_response


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
