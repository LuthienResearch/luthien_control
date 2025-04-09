"""Unit tests for PrepareBackendHeadersPolicy."""

import pytest
from httpx import Headers, Request
from unittest.mock import MagicMock

from luthien_control.config.settings import Settings
from luthien_control.control_policy.prepare_backend_headers import PrepareBackendHeadersPolicy
from luthien_control.core.context import TransactionContext

# Mark all tests in this module as async tests
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_settings() -> MagicMock:
    settings = MagicMock(spec=Settings)
    settings.get_backend_url.return_value = "https://api.mock-backend.com:443/some/path"
    return settings


@pytest.fixture
def policy(mock_settings: MagicMock) -> PrepareBackendHeadersPolicy:
    return PrepareBackendHeadersPolicy(settings=mock_settings)


@pytest.fixture
def base_context_request() -> Request:
    """Creates a base httpx.Request for the context."""
    # This request simulates the state *after* InitializeContextPolicy has run
    return Request(
        method="POST",
        # The URL here is the initial one from the incoming request
        url="http://proxy.luthien.local/v1/chat",
        headers=Headers(
            {
                # Headers copied directly from incoming request by InitializeContextPolicy
                "content-type": "application/json",
                "accept": "*/*",
                "host": "proxy.luthien.local",  # Original host, should be replaced
                "content-length": "100",  # Hop-by-hop, should be removed
                "transfer-encoding": "chunked",  # Hop-by-hop, should be removed
                "connection": "keep-alive",  # Hop-by-hop, should be removed
                "x-custom-incoming": "value1",
                "accept-encoding": "gzip, deflate, br",  # Should be replaced by 'identity'
            }
        ),
        content=b'{"test": "data"}',
    )


@pytest.fixture
def base_context(base_context_request: Request) -> TransactionContext:
    """Creates a base TransactionContext with a request."""
    ctx = TransactionContext(transaction_id="tx-header-test")
    ctx.request = base_context_request
    # Simulate raw body stored by previous policy
    ctx.data["raw_request_body"] = b'{"test": "data"}'
    return ctx


async def test_prepare_headers_success(policy: PrepareBackendHeadersPolicy, base_context: TransactionContext):
    """Test successful header preparation, filtering, and setting."""
    # Act
    updated_context = await policy.apply(base_context)

    # Assert
    assert updated_context is base_context
    assert updated_context.request is not None
    headers = updated_context.request.headers
    # Check required headers
    assert headers.get("host") == "api.mock-backend.com"  # Host replaced with backend hostname
    assert headers.get("accept-encoding") == "identity"
    # Check preserved headers
    assert headers.get("content-type") == "application/json"
    assert headers.get("accept") == "*/*"
    assert headers.get("x-custom-incoming") == "value1"
    # Check filtered hop-by-hop headers
    assert "content-length" not in headers
    assert "transfer-encoding" not in headers
    assert "connection" not in headers
    # Check original Host was replaced
    assert headers.get("host") != "proxy.luthien.local"
    # Check original Accept-Encoding was replaced
    assert headers.get("accept-encoding") != "gzip, deflate, br"
    # Check URL and content remain unchanged by this policy
    assert str(updated_context.request.url) == "http://proxy.luthien.local/v1/chat"
    assert updated_context.request.content == b'{"test": "data"}'


async def test_prepare_headers_no_request(policy: PrepareBackendHeadersPolicy):
    """Test behavior when context.request is None."""
    # Arrange
    context_no_request = TransactionContext(transaction_id="tx-no-req")
    context_no_request.request = None

    # Act & Assert
    with pytest.raises(ValueError, match="Cannot prepare headers: context.request is None"):
        await policy.apply(context_no_request)


async def test_prepare_headers_invalid_backend_url(mock_settings: MagicMock, base_context: TransactionContext):
    """Test behavior with invalid BACKEND_URL."""
    # Arrange
    mock_settings.get_backend_url.side_effect = ValueError("Invalid URL config")
    policy_bad_settings = PrepareBackendHeadersPolicy(settings=mock_settings)

    # Act & Assert
    with pytest.raises(ValueError, match="Invalid backend_url configuration: Invalid URL config"):
        await policy_bad_settings.apply(base_context)


async def test_prepare_headers_backend_url_no_hostname(mock_settings: MagicMock, base_context: TransactionContext):
    """Test behavior when BACKEND_URL cannot be parsed for hostname."""
    # Arrange
    mock_settings.get_backend_url.return_value = "http://?query=only"  # Invalid URL, no hostname
    policy_bad_url = PrepareBackendHeadersPolicy(settings=mock_settings)

    # Act & Assert
    with pytest.raises(ValueError, match="Could not parse hostname from BACKEND_URL"):
        await policy_bad_url.apply(base_context)


# TODO: Test with different header casing (incoming and hop-by-hop)
# TODO: Test case where backend URL includes port number
