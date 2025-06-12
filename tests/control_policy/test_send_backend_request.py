"""Unit tests for ControlPolicy SendBackendRequestPolicy."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from luthien_control.control_policy.send_backend_request import SendBackendRequestPolicy
from luthien_control.core.tracked_context import TrackedContext
from luthien_control.settings import Settings

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
    # Dependencies are now resolved via the container in apply()
    return SendBackendRequestPolicy(
        name="test-policy",
    )


@pytest.fixture
def base_context() -> TrackedContext:
    """Provides a basic TrackedContext with a simple request."""
    context = TrackedContext(transaction_id=uuid.uuid4())

    # Use TrackedContext API to set request
    context.update_request(
        method="POST",
        url="http://proxy.test/some/path",
        headers={
            "host": "proxy.test",
            "content-type": "application/json",
            "accept": "*/*",
            "x-client-header": "client-value",
            "content-length": "18",  # Excluded header
            "authorization": "Bearer client-token",  # Excluded header
        },
        content=b'{"input": "test"}',
    )

    return context


async def test_apply_success(
    policy: SendBackendRequestPolicy,
    base_context: TrackedContext,
    mock_http_client: AsyncMock,
    mock_settings: MagicMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test successful request sending and response handling."""
    # Mock the response from the backend
    mock_backend_response = MagicMock(spec=httpx.Response)
    mock_backend_response.status_code = 200
    mock_backend_response.content = b'{"response": "success"}'
    mock_backend_response.headers = httpx.Headers({"content-type": "application/json"})
    mock_backend_response.aread = AsyncMock()
    # Configure the mock client to return this response
    mock_http_client.send.return_value = mock_backend_response

    # Configure mock container
    mock_container.settings = mock_settings
    mock_container.http_client = mock_http_client

    updated_context = await policy.apply(base_context, container=mock_container, session=mock_db_session)

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
    assert sent_headers.get("Host") == "api.test-backend.com"
    assert sent_headers.get("Authorization") == "Bearer test-backend-api-key"
    assert sent_headers.get("Accept-Encoding") == "identity"
    assert sent_headers.get("content-type") == "application/json"  # Preserved
    assert sent_headers.get("accept") == "*/*"  # Preserved
    assert sent_headers.get("x-client-header") == "client-value"  # Preserved
    # Check excluded headers
    assert sent_headers.get("Authorization") != "Bearer client-token"  # Original auth replaced

    # Verify response was stored in context
    assert base_context.response is not None
    assert base_context.response.status_code == 200
    assert base_context.response.content == b'{"response": "success"}'


async def test_apply_builds_correct_url_no_base_slash(
    policy: SendBackendRequestPolicy,
    base_context: TrackedContext,
    mock_http_client: AsyncMock,
    mock_settings: MagicMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Verify URL construction with no trailing slash on the base backend URL."""

    # Create a new context with the specific URL we want to test
    test_context = TrackedContext(transaction_id=base_context.transaction_id)
    test_context.update_request(
        method="POST",
        url="http://proxy.test/specific/endpoint",
        headers={
            "host": "proxy.test",
            "content-type": "application/json",
        },
        content=b'{"input": "test"}',
    )

    mock_settings.get_backend_url.return_value = "http://backend.internal:8080/api"  # No trailing slash
    expected_url = "http://backend.internal:8080/api/specific/endpoint"

    # Mock the response from the backend
    mock_backend_response = MagicMock(spec=httpx.Response)
    mock_backend_response.status_code = 200
    mock_backend_response.content = b'{"response": "success"}'
    mock_backend_response.headers = httpx.Headers({"content-type": "application/json"})
    mock_backend_response.aread = AsyncMock()
    mock_http_client.send.return_value = mock_backend_response

    # Configure mock container
    mock_container.settings = mock_settings
    mock_container.http_client = mock_http_client

    # Patch Settings and Act
    with patch("luthien_control.control_policy.send_backend_request.Settings", return_value=mock_settings):
        await policy.apply(test_context, container=mock_container, session=mock_db_session)

    # Assert
    mock_http_client.send.assert_awaited_once()
    sent_request = mock_http_client.send.await_args.args[0]
    assert str(sent_request.url) == expected_url


async def test_apply_builds_correct_url_with_base_slash(
    policy: SendBackendRequestPolicy,
    base_context: TrackedContext,
    mock_http_client: AsyncMock,
    mock_settings: MagicMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Verify URL construction with a trailing slash on the base backend URL."""

    # Create a new context with the specific URL we want to test
    test_context = TrackedContext(transaction_id=base_context.transaction_id)
    test_context.update_request(
        method="POST",
        url="http://proxy.test/specific/endpoint",
        headers={
            "host": "proxy.test",
            "content-type": "application/json",
        },
        content=b'{"input": "test"}',
    )

    mock_settings.get_backend_url.return_value = "http://backend.internal:8080/api/"  # Trailing slash
    expected_url = "http://backend.internal:8080/api/specific/endpoint"

    # Mock the response from the backend
    mock_backend_response = MagicMock(spec=httpx.Response)
    mock_backend_response.status_code = 200
    mock_backend_response.content = b'{"response": "success"}'
    mock_backend_response.headers = httpx.Headers({"content-type": "application/json"})
    mock_backend_response.aread = AsyncMock()
    mock_http_client.send.return_value = mock_backend_response

    # Configure mock container
    mock_container.settings = mock_settings
    mock_container.http_client = mock_http_client

    # Patch Settings and Act
    with patch("luthien_control.control_policy.send_backend_request.Settings", return_value=mock_settings):
        await policy.apply(test_context, container=mock_container, session=mock_db_session)

    # Assert
    mock_http_client.send.assert_awaited_once()
    sent_request = mock_http_client.send.await_args.args[0]
    assert str(sent_request.url) == expected_url


async def test_apply_builds_correct_url_root_client_path(
    policy: SendBackendRequestPolicy,
    base_context: TrackedContext,
    mock_http_client: AsyncMock,
    mock_settings: MagicMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Verify URL construction when the client request path is '/'."""

    # Create a new context with the root path we want to test
    test_context = TrackedContext(transaction_id=base_context.transaction_id)
    test_context.update_request(
        method="POST",
        url="http://proxy.test/",  # Root path
        headers={
            "host": "proxy.test",
            "content-type": "application/json",
        },
        content=b'{"input": "test"}',
    )

    mock_settings.get_backend_url.return_value = "http://backend.internal:8080/api"
    expected_url = "http://backend.internal:8080/api/"  # Should join correctly

    # Mock the response from the backend
    mock_backend_response = MagicMock(spec=httpx.Response)
    mock_backend_response.status_code = 200
    mock_backend_response.content = b'{"response": "success"}'
    mock_backend_response.headers = httpx.Headers({"content-type": "application/json"})
    mock_backend_response.aread = AsyncMock()
    mock_http_client.send.return_value = mock_backend_response

    # Configure mock container
    mock_container.settings = mock_settings
    mock_container.http_client = mock_http_client

    # Patch Settings and Act
    with patch("luthien_control.control_policy.send_backend_request.Settings", return_value=mock_settings):
        await policy.apply(test_context, container=mock_container, session=mock_db_session)

    # Assert
    mock_http_client.send.assert_awaited_once()
    sent_request = mock_http_client.send.await_args.args[0]
    assert str(sent_request.url) == expected_url


async def test_apply_prepares_correct_headers(
    policy: SendBackendRequestPolicy,
    base_context: TrackedContext,
    mock_http_client: AsyncMock,
    mock_settings: MagicMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Verify headers sent to the backend are prepared correctly."""

    # Use specific settings for this test
    mock_settings.get_backend_url.return_value = "https://secure-backend.org"
    mock_settings.get_openai_api_key.return_value = "backend-key-for-header-test"

    assert base_context.request is not None
    # Capture original headers BEFORE applying the policy
    original_headers = base_context.request.headers

    # Mock the response from the backend
    mock_backend_response = MagicMock(spec=httpx.Response)
    mock_backend_response.status_code = 200
    mock_backend_response.content = b'{"response": "success"}'
    mock_backend_response.headers = httpx.Headers({"content-type": "application/json"})
    mock_backend_response.aread = AsyncMock()
    mock_http_client.send.return_value = mock_backend_response

    # Configure mock container
    mock_container.settings = mock_settings
    mock_container.http_client = mock_http_client

    # Patch Settings and Act
    with patch("luthien_control.control_policy.send_backend_request.Settings", return_value=mock_settings):
        await policy.apply(base_context, container=mock_container, session=mock_db_session)

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
    base_context: TrackedContext,
    mock_http_client: AsyncMock,
    mock_settings: MagicMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test handling of httpx.RequestError during backend communication."""
    # Arrange
    error_message = "Connection refused"
    # Create a new context with the specific URL for error testing
    test_context = TrackedContext(transaction_id=base_context.transaction_id)
    test_context.update_request(
        method="POST",
        url="https://api.test-backend.com/v1/some/path",
        headers={
            "host": "api.test-backend.com",
            "content-type": "application/json",
        },
        content=b'{"input": "test"}',
    )
    # Use an httpx.Request object for the error (as expected by httpx.RequestError)
    request_for_error = httpx.Request("POST", "https://api.test-backend.com/v1/some/path")
    mock_http_client.send.side_effect = httpx.RequestError(error_message, request=request_for_error)

    # Patch Settings and Act/Assert
    with patch("luthien_control.control_policy.send_backend_request.Settings", return_value=mock_settings):
        with pytest.raises(httpx.RequestError, match=error_message) as exc_info:
            await policy.apply(test_context, container=mock_container, session=mock_db_session)

    # Optional: Assert that the raised exception is the same instance
    assert exc_info.value is mock_http_client.send.side_effect
    # Verify send was called
    mock_http_client.send.assert_awaited_once()
    # Verify no response was stored
    assert test_context.response is None


async def test_apply_handles_httpx_timeout_error(
    policy: SendBackendRequestPolicy,
    base_context: TrackedContext,
    mock_http_client: AsyncMock,
    mock_settings: MagicMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test handling of httpx.TimeoutException during backend communication."""
    # Arrange
    error_message = "Read timeout"
    # Create a new context with the specific URL for timeout testing
    test_context = TrackedContext(transaction_id=base_context.transaction_id)
    test_context.update_request(
        method="POST",
        url="https://api.test-backend.com/v1/some/path",
        headers={
            "host": "api.test-backend.com",
            "content-type": "application/json",
        },
        content=b'{"input": "test"}',
    )
    # Use an httpx.Request object for the error (as expected by httpx.TimeoutException)
    request_for_error = httpx.Request("POST", "https://api.test-backend.com/v1/some/path")
    mock_http_client.send.side_effect = httpx.TimeoutException(error_message, request=request_for_error)

    # Patch Settings and Act/Assert
    with patch("luthien_control.control_policy.send_backend_request.Settings", return_value=mock_settings):
        with pytest.raises(httpx.TimeoutException, match=error_message) as exc_info:
            await policy.apply(test_context, container=mock_container, session=mock_db_session)

    # Optional: Assert that the raised exception is the same instance
    assert exc_info.value is mock_http_client.send.side_effect
    # Verify send was called
    mock_http_client.send.assert_awaited_once()
    # Verify no response was stored
    assert test_context.response is None


async def test_apply_raises_if_context_request_is_none(
    policy: SendBackendRequestPolicy,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that apply raises ValueError if context.request is None."""
    # Create a context without setting a request (request will be None by default)
    context_no_request = TrackedContext(transaction_id=uuid.uuid4())
    with pytest.raises(ValueError, match="context.request is None"):
        await policy.apply(context_no_request, container=mock_container, session=mock_db_session)


async def test_apply_handles_invalid_backend_url(
    policy: SendBackendRequestPolicy,
    base_context: TrackedContext,
    mock_http_client: AsyncMock,
    mock_settings: MagicMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that apply raises ValueError if BACKEND_URL is invalid for host parsing."""
    mock_settings.get_backend_url.return_value = "invalid-url"  # Invalid URL

    with patch("luthien_control.control_policy.send_backend_request.Settings", return_value=mock_settings):
        with pytest.raises(ValueError, match="Could not determine backend Host from BACKEND_URL"):
            await policy.apply(base_context, container=mock_container, session=mock_db_session)

    mock_http_client.send.assert_not_called()


async def test_apply_with_no_backend_url(
    policy: SendBackendRequestPolicy,
    base_context: TrackedContext,
    mock_http_client: AsyncMock,
    mock_settings: MagicMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that apply raises ValueError if BACKEND_URL is not set."""
    mock_settings.get_backend_url.return_value = None
    with pytest.raises(ValueError, match="BACKEND_URL is not configured."):
        await policy.apply(base_context, container=mock_container, session=mock_db_session)

    mock_http_client.send.assert_not_called()


async def test_apply_http_client_weird_exception(
    policy: SendBackendRequestPolicy,
    base_context: TrackedContext,
    mock_http_client: AsyncMock,
    mock_settings: MagicMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test exception handling for unexpected exceptions from the http client."""
    mock_http_client.send.side_effect = Exception("Unexpected error")
    with pytest.raises(Exception, match="Unexpected error"):
        await policy.apply(base_context, container=mock_container, session=mock_db_session)

    mock_http_client.send.assert_awaited_once()
    assert base_context.response is None


async def test_backend_request_policy_serialize_from_serialized():
    """Test serialization and deserialization of the policy."""
    policy = SendBackendRequestPolicy(name="test-policy")
    serialized = policy.serialize()
    assert serialized == {"name": "test-policy"}
    deserialized_policy = SendBackendRequestPolicy.from_serialized(serialized)
    assert deserialized_policy.name == "test-policy"
