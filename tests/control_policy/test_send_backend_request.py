"""Unit tests for ControlPolicy SendBackendRequestPolicy."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from luthien_control.config.settings import Settings
from luthien_control.control_policy.send_backend_request import SendBackendRequestPolicy
from luthien_control.core.transaction_context import TransactionContext

# Mark all tests in this module as async tests
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_settings() -> MagicMock:
    """Provides a mock Settings object."""
    settings = MagicMock(spec=Settings)
    settings.get_backend_url.return_value = "https://api.test-backend.com/v1"
    settings.get_openai_api_key.return_value = "test-backend-api-key"
    return settings


@pytest.fixture
def mock_http_client() -> AsyncMock:
    """Provides a mock httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def policy(mock_http_client: AsyncMock, mock_settings: MagicMock) -> SendBackendRequestPolicy:
    """Provides an instance of the policy with a mock client."""
    return SendBackendRequestPolicy(
        http_client=mock_http_client,
        settings=mock_settings,
        name="test-policy",
    )


@pytest.fixture
def base_context() -> TransactionContext:
    """Provides a basic TransactionContext with a simple request."""
    context = TransactionContext(transaction_id="tx-send-test")
    mock_request = MagicMock(spec=httpx.Request)
    mock_request.method = "POST"
    mock_request.url = httpx.URL("http://proxy.test/some/path")
    mock_request.headers = httpx.Headers(
        [
            (b"host", b"proxy.test"),
            (b"content-type", b"application/json"),
            (b"accept", b"*/*"),
            (b"x-client-header", b"client-value"),
            (b"content-length", b"18"),  # Excluded header
            (b"authorization", b"Bearer client-token"),  # Excluded header
        ]
    )
    mock_request.read = AsyncMock(return_value=b'{"input": "test"}')
    mock_request.stream = None  # Simulate a request body that can be read

    context.request = mock_request
    return context


async def test_apply_success(
    policy: SendBackendRequestPolicy,
    base_context: TransactionContext,
    mock_http_client: AsyncMock,
    mock_settings: MagicMock,
):
    """Test successful request sending and response handling."""
    # Mock the response from the backend
    mock_backend_response = MagicMock(spec=httpx.Response)
    mock_backend_response.status_code = 200
    # Simulate response body being read by httpx upon receiving response
    mock_backend_response.content = b'{"response": "success"}'
    # Configure the mock client to return this response
    mock_http_client.send.return_value = mock_backend_response

    # Patch Settings within the test scope
    with patch("luthien_control.control_policy.send_backend_request.Settings", return_value=mock_settings):
        updated_context = await policy.apply(base_context)

    # Assert
    assert updated_context is base_context
    # Verify the http client was called
    mock_http_client.send.assert_awaited_once()
    # Get the request object passed to send
    sent_request = mock_http_client.send.await_args.args[0]

    # Assertions on the request sent to the backend
    assert sent_request.method == "POST"
    assert str(sent_request.url) == "https://api.test-backend.com/v1/some/path"
    # Check specific headers
    sent_headers = sent_request.headers
    assert sent_headers.get("host") == "api.test-backend.com"
    assert sent_headers.get("authorization") == "Bearer test-backend-api-key"
    assert sent_headers.get("accept-encoding") == "identity"
    assert sent_headers.get("content-type") == "application/json"  # Preserved
    assert sent_headers.get("accept") == "*/*"  # Preserved
    assert sent_headers.get("x-client-header") == "client-value"  # Preserved
    # Check excluded headers
    assert sent_headers.get("authorization") != "Bearer client-token"  # Original auth replaced

    # Assert that the backend response is stored in the context
    assert "backend_response" in updated_context.data
    assert updated_context.data["backend_response"] is mock_backend_response
    # Verify the mocked response content was accessed (implicitly by httpx/policy)
    assert mock_backend_response.content is not None  # Ensures the attribute was set/accessed


async def test_apply_builds_correct_url_no_base_slash(
    policy: SendBackendRequestPolicy,
    base_context: TransactionContext,
    mock_http_client: AsyncMock,
    mock_settings: MagicMock,
):
    """Verify URL construction with no trailing slash on the base backend URL."""

    original_client_url = httpx.URL("http://proxy.test/specific/endpoint")
    base_context.request.url = original_client_url
    mock_settings.get_backend_url.return_value = "http://backend.internal:8080/api"  # No trailing slash
    expected_url = "http://backend.internal:8080/api/specific/endpoint"

    # Patch Settings and Act
    with patch("luthien_control.control_policy.send_backend_request.Settings", return_value=mock_settings):
        await policy.apply(base_context)

    # Assert
    mock_http_client.send.assert_awaited_once()
    sent_request = mock_http_client.send.await_args.args[0]
    assert str(sent_request.url) == expected_url


async def test_apply_builds_correct_url_with_base_slash(
    policy: SendBackendRequestPolicy,
    base_context: TransactionContext,
    mock_http_client: AsyncMock,
    mock_settings: MagicMock,
):
    """Verify URL construction with a trailing slash on the base backend URL."""

    original_client_url = httpx.URL("http://proxy.test/specific/endpoint")
    base_context.request.url = original_client_url
    mock_settings.get_backend_url.return_value = "http://backend.internal:8080/api/"  # Trailing slash
    expected_url = "http://backend.internal:8080/api/specific/endpoint"

    # Patch Settings and Act
    with patch("luthien_control.control_policy.send_backend_request.Settings", return_value=mock_settings):
        await policy.apply(base_context)

    # Assert
    mock_http_client.send.assert_awaited_once()
    sent_request = mock_http_client.send.await_args.args[0]
    assert str(sent_request.url) == expected_url


async def test_apply_builds_correct_url_root_client_path(
    policy: SendBackendRequestPolicy,
    base_context: TransactionContext,
    mock_http_client: AsyncMock,
    mock_settings: MagicMock,
):
    """Verify URL construction when the client request path is '/'."""

    root_client_url = httpx.URL("http://proxy.test/")  # Root path
    base_context.request.url = root_client_url
    mock_settings.get_backend_url.return_value = "http://backend.internal:8080/api"
    expected_url = "http://backend.internal:8080/api/"  # Should join correctly

    # Patch Settings and Act
    with patch("luthien_control.control_policy.send_backend_request.Settings", return_value=mock_settings):
        await policy.apply(base_context)

    # Assert
    mock_http_client.send.assert_awaited_once()
    sent_request = mock_http_client.send.await_args.args[0]
    assert str(sent_request.url) == expected_url


async def test_apply_prepares_correct_headers(
    policy: SendBackendRequestPolicy,
    base_context: TransactionContext,
    mock_http_client: AsyncMock,
    mock_settings: MagicMock,
):
    """Verify headers sent to the backend are prepared correctly."""

    # Use specific settings for this test
    mock_settings.get_backend_url.return_value = "https://secure-backend.org"
    mock_settings.get_openai_api_key.return_value = "backend-key-for-header-test"

    # Capture original headers BEFORE applying the policy
    original_headers = base_context.request.headers.copy()

    # Patch Settings and Act
    with patch("luthien_control.control_policy.send_backend_request.Settings", return_value=mock_settings):
        await policy.apply(base_context)

    # Assert
    mock_http_client.send.assert_awaited_once()
    sent_request = mock_http_client.send.await_args.args[0]
    sent_headers = sent_request.headers

    # Check Host header based on mock_settings
    assert sent_headers.get("host") == "secure-backend.org"
    # Check Authorization header based on mock_settings
    assert sent_headers.get("authorization") == "Bearer backend-key-for-header-test"
    # Check forced Accept-Encoding
    assert sent_headers.get("accept-encoding") == "identity"
    # Check content-length is set correctly
    assert sent_headers.get("content-length") == "18"
    # Check preserved headers from base_context fixture
    assert sent_headers.get("content-type") == "application/json"
    assert sent_headers.get("accept") == "*/*"
    assert sent_headers.get("x-client-header") == "client-value"
    # Check excluded headers from base_context fixture
    assert "connection" not in sent_headers  # Another hop-by-hop header
    # Ensure original client Host and Authorization were replaced/excluded
    # Use the captured original_headers here
    assert sent_headers.get("host") != original_headers.get("host")
    assert sent_headers.get("authorization") != original_headers.get("authorization")


async def test_apply_handles_httpx_request_error(
    policy: SendBackendRequestPolicy,
    base_context: TransactionContext,
    mock_http_client: AsyncMock,
    mock_settings: MagicMock,
):
    """Test handling of httpx.RequestError during backend communication."""
    # Arrange
    error_message = "Connection refused"
    # Ensure the request object passed to the exception has a URL for logging
    request_for_error = base_context.request
    if request_for_error:
        request_for_error.url = httpx.URL("https://api.test-backend.com/v1/some/path")
    mock_http_client.send.side_effect = httpx.RequestError(error_message, request=request_for_error)

    # Patch Settings and Act/Assert
    with patch("luthien_control.control_policy.send_backend_request.Settings", return_value=mock_settings):
        with pytest.raises(httpx.RequestError, match=error_message) as exc_info:
            await policy.apply(base_context)

    # Optional: Assert that the raised exception is the same instance
    assert exc_info.value is mock_http_client.send.side_effect
    # Verify send was called
    mock_http_client.send.assert_awaited_once()
    # Verify no response was stored
    assert "backend_response" not in base_context.data


async def test_apply_handles_httpx_timeout_error(
    policy: SendBackendRequestPolicy,
    base_context: TransactionContext,
    mock_http_client: AsyncMock,
    mock_settings: MagicMock,
):
    """Test handling of httpx.TimeoutException during backend communication."""
    # Arrange
    error_message = "Read timeout"
    # Ensure the request object passed to the exception has a URL for logging
    request_for_error = base_context.request
    if request_for_error:
        request_for_error.url = httpx.URL("https://api.test-backend.com/v1/some/path")
    mock_http_client.send.side_effect = httpx.TimeoutException(error_message, request=request_for_error)

    # Patch Settings and Act/Assert
    with patch("luthien_control.control_policy.send_backend_request.Settings", return_value=mock_settings):
        with pytest.raises(httpx.TimeoutException, match=error_message) as exc_info:
            await policy.apply(base_context)

    # Optional: Assert that the raised exception is the same instance
    assert exc_info.value is mock_http_client.send.side_effect
    # Verify send was called
    mock_http_client.send.assert_awaited_once()
    # Verify no response was stored
    assert "backend_response" not in base_context.data


async def test_apply_raises_if_context_request_is_none(policy: SendBackendRequestPolicy):
    """Test that apply raises ValueError if context.request is None."""
    context_no_request = TransactionContext(transaction_id="tx-no-request")
    with pytest.raises(ValueError, match="context.request is None"):
        await policy.apply(context_no_request)


async def test_apply_handles_invalid_backend_url(
    policy: SendBackendRequestPolicy,
    base_context: TransactionContext,
    mock_http_client: AsyncMock,
    mock_settings: MagicMock,
):
    """Test that apply raises ValueError if BACKEND_URL is invalid for host parsing."""
    mock_settings.get_backend_url.return_value = "invalid-url"  # Invalid URL

    with patch("luthien_control.control_policy.send_backend_request.Settings", return_value=mock_settings):
        with pytest.raises(ValueError, match="Could not determine backend Host"):
            await policy.apply(base_context)


# --- Serialization Tests ---


async def test_send_backend_request_policy_serialization(
    policy: SendBackendRequestPolicy,
):
    """Test that SendBackendRequestPolicy can be serialized and deserialized correctly."""
    # Arrange
    # 'policy' fixture already provides an instance
    original_policy = policy

    # Act
    serialized_data = original_policy.serialize()
    rehydrated_policy = await SendBackendRequestPolicy.from_serialized(
        http_client=mock_http_client, config=serialized_data, settings=mock_settings
    )

    # Assert
    assert isinstance(serialized_data, dict)
    # Since serialize returns an empty dict, there's not much to assert on the dict itself
    assert serialized_data == {"name": "test-policy"}

    assert isinstance(rehydrated_policy, SendBackendRequestPolicy)
    # Check if the rehydrated policy has the correct http_client
    assert rehydrated_policy.http_client is mock_http_client
