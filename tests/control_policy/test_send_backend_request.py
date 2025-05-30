"""Unit tests for ControlPolicy SendBackendRequestPolicy."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from luthien_control.control_policy.send_backend_request import SendBackendRequestPolicy
from luthien_control.core.transaction_context import TransactionContext
from luthien_control.settings import Settings

# Mark all tests in this module as async tests
pytestmark = pytest.mark.asyncio


@pytest.fixture
def test_settings() -> Settings:
    """Provides a real Settings object for testing."""
    import os
    os.environ["BACKEND_URL"] = "https://api.test-backend.com/v1"
    os.environ["OPENAI_API_KEY"] = "test-backend-api-key"
    return Settings()


@pytest.fixture
def mock_http_client() -> AsyncMock:
    """Provides a mock httpx.AsyncClient."""
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def policy() -> SendBackendRequestPolicy:
    """Provides an instance of the policy."""
    return SendBackendRequestPolicy(name="test-policy")


@pytest.fixture
def base_context() -> TransactionContext:
    """Provides a basic TransactionContext with a real request."""
    context = TransactionContext(transaction_id=uuid.uuid4())

    real_request = httpx.Request(
        method="POST",
        url="http://proxy.test/some/path",
        headers={
            "host": "proxy.test",
            "content-type": "application/json",
            "accept": "*/*",
            "x-client-header": "client-value",
            "content-length": "18",
            "authorization": "Bearer client-token",
        },
        content=b'{"input": "test"}'
    )

    context.request = real_request
    return context


async def test_apply_success(
    policy: SendBackendRequestPolicy,
    base_context: TransactionContext,
    mock_http_client: AsyncMock,
    test_settings: Settings,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test successful request sending and response handling."""
    # Mock the response from the backend
    mock_backend_response = MagicMock(spec=httpx.Response)
    mock_backend_response.status_code = 200
    # Simulate response body being read by httpx upon receiving response
    mock_backend_response.content = b'{"response": "success"}'
    # Configure the mock client to return this response
    mock_http_client.send.return_value = mock_backend_response

    # Configure container to return real settings
    mock_container.settings = test_settings
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
    assert sent_headers.get("host") == "api.test-backend.com"
    assert sent_headers.get("authorization") == "Bearer test-backend-api-key"
    assert sent_headers.get("accept-encoding") == "identity"
    assert sent_headers.get("content-type") == "application/json"  # Preserved
    assert sent_headers.get("accept") == "*/*"  # Preserved
    assert sent_headers.get("x-client-header") == "client-value"  # Preserved
    # Check excluded headers
    assert sent_headers.get("authorization") != "Bearer client-token"  # Original auth replaced

    # Assert that the backend response is stored in the context
    assert updated_context.response is mock_backend_response
    # Verify the mocked response content was accessed (implicitly by httpx/policy)
    assert mock_backend_response.content is not None  # Ensures the attribute was set/accessed


async def test_apply_builds_correct_url_no_base_slash(
    policy: SendBackendRequestPolicy,
    base_context: TransactionContext,
    mock_http_client: AsyncMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Verify URL construction with no trailing slash on the base backend URL."""

    import os
    os.environ["BACKEND_URL"] = "http://backend.internal:8080/api"  # No trailing slash
    test_settings = Settings()

    original_client_url = httpx.URL("http://proxy.test/specific/endpoint")
    assert base_context.request is not None
    base_context.request = httpx.Request(
        method=base_context.request.method,
        url=original_client_url,
        headers=base_context.request.headers,
        content=base_context.request.content
    )
    expected_url = "http://backend.internal:8080/api/specific/endpoint"

    # Configure container and Act
    mock_container.settings = test_settings
    mock_container.http_client = mock_http_client
    await policy.apply(base_context, container=mock_container, session=mock_db_session)

    # Assert
    mock_http_client.send.assert_awaited_once()
    sent_request = mock_http_client.send.await_args.args[0]
    assert str(sent_request.url) == expected_url


async def test_apply_builds_correct_url_with_base_slash(
    policy: SendBackendRequestPolicy,
    base_context: TransactionContext,
    mock_http_client: AsyncMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Verify URL construction with a trailing slash on the base backend URL."""

    import os
    os.environ["BACKEND_URL"] = "http://backend.internal:8080/api/"  # Trailing slash
    test_settings = Settings()

    original_client_url = httpx.URL("http://proxy.test/specific/endpoint")
    assert base_context.request is not None
    base_context.request = httpx.Request(
        method=base_context.request.method,
        url=original_client_url,
        headers=base_context.request.headers,
        content=base_context.request.content
    )
    expected_url = "http://backend.internal:8080/api/specific/endpoint"

    # Configure container and Act
    mock_container.settings = test_settings
    mock_container.http_client = mock_http_client
    await policy.apply(base_context, container=mock_container, session=mock_db_session)

    # Assert
    mock_http_client.send.assert_awaited_once()
    sent_request = mock_http_client.send.await_args.args[0]
    assert str(sent_request.url) == expected_url


async def test_apply_builds_correct_url_root_client_path(
    policy: SendBackendRequestPolicy,
    base_context: TransactionContext,
    mock_http_client: AsyncMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Verify URL construction when the client request path is '/'."""

    import os
    os.environ["BACKEND_URL"] = "http://backend.internal:8080/api"
    test_settings = Settings()

    root_client_url = httpx.URL("http://proxy.test/")  # Root path
    assert base_context.request is not None
    base_context.request = httpx.Request(
        method=base_context.request.method,
        url=root_client_url,
        headers=base_context.request.headers,
        content=base_context.request.content
    )
    expected_url = "http://backend.internal:8080/api/"  # Should join correctly

    # Configure container and Act
    mock_container.settings = test_settings
    mock_container.http_client = mock_http_client
    await policy.apply(base_context, container=mock_container, session=mock_db_session)

    # Assert
    mock_http_client.send.assert_awaited_once()
    sent_request = mock_http_client.send.await_args.args[0]
    assert str(sent_request.url) == expected_url


async def test_apply_prepares_correct_headers(
    policy: SendBackendRequestPolicy,
    base_context: TransactionContext,
    mock_http_client: AsyncMock,
    test_settings: Settings,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Verify headers sent to the backend are prepared correctly."""

    # Use specific settings for this test
    import os
    os.environ["BACKEND_URL"] = "https://secure-backend.org"
    os.environ["OPENAI_API_KEY"] = "backend-key-for-header-test"
    test_settings_for_headers = Settings()

    assert base_context.request is not None
    # Capture original headers BEFORE applying the policy
    original_headers = base_context.request.headers.copy()

    # Configure container and Act
    mock_container.settings = test_settings_for_headers
    mock_container.http_client = mock_http_client
    await policy.apply(base_context, container=mock_container, session=mock_db_session)

    # Assert
    mock_http_client.send.assert_awaited_once()
    sent_request = mock_http_client.send.await_args.args[0]
    sent_headers = sent_request.headers

    # Check Host header based on test settings
    assert sent_headers.get("host") == "secure-backend.org"
    # Check Authorization header based on test settings
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
    test_settings: Settings,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test handling of httpx.RequestError during backend communication."""
    # Arrange
    error_message = "Connection refused"
    # Ensure the request object passed to the exception has a URL for logging
    request_for_error = base_context.request
    if request_for_error:
        request_for_error.url = httpx.URL("https://api.test-backend.com/v1/some/path")
    mock_http_client.send.side_effect = httpx.RequestError(error_message, request=request_for_error)

    # Configure container and Act/Assert
    mock_container.settings = test_settings
    mock_container.http_client = mock_http_client
    with pytest.raises(httpx.RequestError, match=error_message) as exc_info:
        await policy.apply(base_context, container=mock_container, session=mock_db_session)

    # Optional: Assert that the raised exception is the same instance
    assert exc_info.value is mock_http_client.send.side_effect
    # Verify send was called
    mock_http_client.send.assert_awaited_once()
    # Verify no response was stored
    assert base_context.response is None


async def test_apply_handles_httpx_timeout_error(
    policy: SendBackendRequestPolicy,
    base_context: TransactionContext,
    mock_http_client: AsyncMock,
    test_settings: Settings,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test handling of httpx.TimeoutException during backend communication."""
    # Arrange
    error_message = "Read timeout"
    # Ensure the request object passed to the exception has a URL for logging
    request_for_error = base_context.request
    if request_for_error:
        request_for_error.url = httpx.URL("https://api.test-backend.com/v1/some/path")
    mock_http_client.send.side_effect = httpx.TimeoutException(error_message, request=request_for_error)

    # Configure container and Act/Assert
    mock_container.settings = test_settings
    mock_container.http_client = mock_http_client
    with pytest.raises(httpx.TimeoutException, match=error_message) as exc_info:
        await policy.apply(base_context, container=mock_container, session=mock_db_session)

    # Optional: Assert that the raised exception is the same instance
    assert exc_info.value is mock_http_client.send.side_effect
    # Verify send was called
    mock_http_client.send.assert_awaited_once()
    # Verify no response was stored
    assert base_context.response is None


async def test_apply_raises_if_context_request_is_none(
    policy: SendBackendRequestPolicy,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that apply raises ValueError if context.request is None."""
    context_no_request = TransactionContext(transaction_id=uuid.uuid4())
    context_no_request.request = None
    with pytest.raises(ValueError, match="context.request is None"):
        await policy.apply(context_no_request, container=mock_container, session=mock_db_session)


async def test_apply_handles_invalid_backend_url(
    policy: SendBackendRequestPolicy,
    base_context: TransactionContext,
    mock_http_client: AsyncMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that apply raises ValueError if BACKEND_URL is invalid for host parsing."""
    import os
    os.environ["BACKEND_URL"] = "invalid-url"  # Invalid URL
    test_settings = Settings()

    mock_container.settings = test_settings
    mock_container.http_client = mock_http_client
    with pytest.raises(ValueError, match="Invalid BACKEND_URL format"):
        await policy.apply(base_context, container=mock_container, session=mock_db_session)

    mock_http_client.send.assert_not_called()


async def test_apply_with_no_backend_url(
    policy: SendBackendRequestPolicy,
    base_context: TransactionContext,
    mock_http_client: AsyncMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that apply raises ValueError if BACKEND_URL is not set."""
    import os
    if "BACKEND_URL" in os.environ:
        del os.environ["BACKEND_URL"]
    test_settings = Settings()

    mock_container.settings = test_settings
    mock_container.http_client = mock_http_client
    with pytest.raises(ValueError, match="BACKEND_URL is not configured."):
        await policy.apply(base_context, container=mock_container, session=mock_db_session)

    mock_http_client.send.assert_not_called()


async def test_apply_http_client_weird_exception(
    policy: SendBackendRequestPolicy,
    base_context: TransactionContext,
    mock_http_client: AsyncMock,
    test_settings: Settings,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test exception handling for unexpected exceptions from the http client."""
    mock_http_client.send.side_effect = Exception("Unexpected error")
    mock_container.settings = test_settings
    mock_container.http_client = mock_http_client
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
