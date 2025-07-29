"""Tests for SendBackendRequestPolicy."""

import logging
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import openai
import pytest
from luthien_control.api.openai_chat_completions.datatypes import Choice, Message, Usage
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse
from luthien_control.control_policy.send_backend_request import SendBackendRequestPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.raw_request import RawRequest
from luthien_control.core.request import Request
from luthien_control.core.response import Response
from luthien_control.core.transaction import Transaction
from psygnal.containers import EventedDict, EventedList
from sqlalchemy.ext.asyncio import AsyncSession

# --- Helper Functions ---


def create_chat_request(
    model: str = "gpt-4",
    messages: list[Message] | None = None,
    temperature: float = 0.7,
    max_tokens: int = 100,
    api_endpoint: str = "https://api.openai.com/chat/completions",
    api_key: str = "test_key",
) -> Request:
    """Create a chat completions request with sensible defaults."""
    if messages is None:
        messages = [
            Message(role="system", content="You are a helpful assistant."),
            Message(role="user", content="Hello, world!"),
        ]

    return Request(
        payload=OpenAIChatCompletionsRequest(
            model=model,
            messages=EventedList(messages),
            temperature=temperature,
            max_tokens=max_tokens,
        ),
        api_endpoint=api_endpoint,
        api_key=api_key,
    )


def create_chat_response(
    id: str = "chatcmpl-123",
    model: str = "gpt-4",
    content: str = "Hello there!",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
) -> Response:
    """Create a chat completions response with sensible defaults."""
    return Response(
        payload=OpenAIChatCompletionsResponse(
            id=id,
            object="chat.completion",
            created=1677652288,
            model=model,
            choices=EventedList(
                [Choice(index=0, message=Message(role="assistant", content=content), finish_reason="stop")]
            ),
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )
    )


def create_mock_openai_response(
    id: str = "chatcmpl-backend-123",
    content: str = "Hello! How can I help you today?",
) -> dict:
    """Create a mock OpenAI API response dict."""
    return {
        "id": id,
        "object": "chat.completion",
        "created": 1677652388,
        "model": "gpt-4",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 15, "completion_tokens": 10, "total_tokens": 25},
    }


# --- Test Fixtures ---


@pytest.fixture
def sample_transaction() -> Transaction:
    """Provides a Transaction with OpenAI chat completions request for testing."""
    request = create_chat_request()
    response = create_chat_response()
    transaction_data = EventedDict({"test_key": "test_value"})
    return Transaction(openai_request=request, openai_response=response, data=transaction_data)


@pytest.fixture
def mock_openai_client() -> AsyncMock:
    """Provides a mock OpenAI client with default successful response."""
    client = AsyncMock()
    mock_response = MagicMock()
    mock_response.model_dump.return_value = create_mock_openai_response()
    client.chat.completions.create.return_value = mock_response
    return client


@pytest.fixture
def test_container(mock_openai_client: AsyncMock) -> MagicMock:
    """Provides a test dependency container with minimal mocking."""
    container = MagicMock(spec=DependencyContainer)

    # Create settings with real values instead of mocked methods
    settings = MagicMock()
    settings.get_backend_url.return_value = "https://api.test-backend.com"
    settings.get_openai_api_key.return_value = "test-backend-api-key"

    container.settings = settings
    container.create_openai_client.return_value = mock_openai_client
    return container


# --- Test Cases ---


def test_send_backend_request_policy_initialization_default():
    """Test SendBackendRequestPolicy initialization with no args."""
    _ = SendBackendRequestPolicy()


def test_send_backend_request_policy_initialization_custom():
    """Test SendBackendRequestPolicy initialization with custom name."""
    custom_name = "CustomBackendPolicy"
    policy = SendBackendRequestPolicy(name=custom_name)

    assert policy.name == custom_name


@pytest.mark.asyncio
async def test_send_backend_request_policy_no_backend_url(test_container: MagicMock):
    """Test that ValueError is raised when backend URL is not configured."""
    policy = SendBackendRequestPolicy()
    transaction = Transaction(
        openai_request=create_chat_request(api_endpoint=""),
        openai_response=create_chat_response(),
        data=EventedDict(),
    )
    db_session = AsyncMock(spec=AsyncSession)

    with pytest.raises(ValueError, match="Backend URL is not configured"):
        await policy.apply(transaction, test_container, db_session)


@pytest.mark.asyncio
async def test_send_backend_request_policy_no_api_key(test_container: MagicMock):
    """Test that ValueError is raised when API key is not configured."""
    policy = SendBackendRequestPolicy()
    transaction = Transaction(
        openai_request=create_chat_request(api_key=""),
        openai_response=create_chat_response(),
        data=EventedDict(),
    )
    db_session = AsyncMock(spec=AsyncSession)

    with pytest.raises(ValueError, match="OpenAI API key is not configured"):
        await policy.apply(transaction, test_container, db_session)


@pytest.mark.asyncio
async def test_send_backend_request_policy_successful_request(
    sample_transaction: Transaction,
    test_container: MagicMock,
    mock_openai_client: AsyncMock,
):
    """Test successful backend request and response handling."""
    policy = SendBackendRequestPolicy()
    db_session = AsyncMock(spec=AsyncSession)

    result = await policy.apply(sample_transaction, test_container, db_session)

    assert result is sample_transaction

    # Verify OpenAI client was created with correct parameters from transaction.request
    test_container.create_openai_client.assert_called_once_with("https://api.openai.com/chat/completions", "test_key")

    # Verify chat completion was called
    mock_openai_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs

    # Check that the request payload was properly converted and filtered
    assert call_kwargs["model"] == "gpt-4"
    assert len(call_kwargs["messages"]) == 2
    assert call_kwargs["temperature"] == 0.7
    assert call_kwargs["max_tokens"] == 100
    # None values should be filtered out
    assert "stream" not in call_kwargs  # This would be None and should be filtered

    # Verify response was stored in transaction
    assert sample_transaction.openai_response is not None
    assert sample_transaction.openai_response.payload is not None
    assert sample_transaction.openai_response.payload.id == "chatcmpl-backend-123"
    assert sample_transaction.openai_response.payload.model == "gpt-4"
    assert len(sample_transaction.openai_response.payload.choices) == 1
    assert sample_transaction.openai_response.payload.choices[0].message.content == "Hello! How can I help you today?"
    assert sample_transaction.openai_response.payload.usage.total_tokens == 25


@pytest.mark.asyncio
async def test_send_backend_request_policy_logging(
    sample_transaction: Transaction,
    test_container: MagicMock,
    caplog,
):
    """Test that requests and responses are logged correctly."""
    policy = SendBackendRequestPolicy(name="TestPolicy")
    db_session = AsyncMock(spec=AsyncSession)

    with caplog.at_level(logging.INFO):
        await policy.apply(sample_transaction, test_container, db_session)

    # Check request logging
    assert "Sending chat completions request to backend with model 'gpt-4' and 2 messages. (TestPolicy)" in caplog.text

    # Check response logging
    assert "Received backend response with 1 choices and usage:" in caplog.text
    assert "(TestPolicy)" in caplog.text


@pytest.mark.asyncio
async def test_send_backend_request_policy_not_found_error(
    sample_transaction: Transaction,
    test_container: MagicMock,
    mock_openai_client: AsyncMock,
    caplog,
):
    """Test handling of OpenAI NotFoundError (404)."""
    policy = SendBackendRequestPolicy()
    db_session = AsyncMock(spec=AsyncSession)

    # Configure client to raise NotFoundError
    mock_response = httpx.Response(404, request=httpx.Request("POST", "https://api.openai.com/chat/completions"))
    not_found_error = openai.NotFoundError("Resource not found", response=mock_response, body=None)
    mock_openai_client.chat.completions.create.side_effect = not_found_error

    with caplog.at_level(logging.ERROR):
        with pytest.raises(openai.NotFoundError):
            await policy.apply(sample_transaction, test_container, db_session)

    assert (
        "OpenAI NotFoundError during backend request with base url https://api.openai.com/chat/completions"
        in caplog.text
    )


@pytest.mark.asyncio
async def test_send_backend_request_policy_api_timeout_error(
    sample_transaction: Transaction,
    test_container: MagicMock,
    mock_openai_client: AsyncMock,
    caplog,
):
    """Test handling of OpenAI API timeout errors."""
    policy = SendBackendRequestPolicy()
    db_session = AsyncMock(spec=AsyncSession)

    # Configure client to raise timeout error
    mock_request = httpx.Request("POST", "https://api.openai.com/chat/completions")
    timeout_error = openai.APITimeoutError(request=mock_request)
    mock_openai_client.chat.completions.create.side_effect = timeout_error

    with caplog.at_level(logging.ERROR):
        with pytest.raises(openai.APITimeoutError):
            await policy.apply(sample_transaction, test_container, db_session)

    assert "Timeout error during backend request" in caplog.text


@pytest.mark.asyncio
async def test_send_backend_request_policy_api_connection_error(
    sample_transaction: Transaction,
    test_container: MagicMock,
    mock_openai_client: AsyncMock,
    caplog,
):
    """Test handling of OpenAI API connection errors."""
    policy = SendBackendRequestPolicy()
    db_session = AsyncMock(spec=AsyncSession)

    # Configure client to raise connection error
    mock_request = httpx.Request("POST", "https://api.test-backend.com/chat/completions")
    connection_error = openai.APIConnectionError(message="Connection failed", request=mock_request)
    mock_openai_client.chat.completions.create.side_effect = connection_error

    with caplog.at_level(logging.ERROR):
        with pytest.raises(openai.APIConnectionError, match="Connection failed"):
            await policy.apply(sample_transaction, test_container, db_session)

    assert "Connection error during backend request" in caplog.text


@pytest.mark.asyncio
async def test_send_backend_request_policy_api_error(
    sample_transaction: Transaction,
    test_container: MagicMock,
    mock_openai_client: AsyncMock,
    caplog,
):
    """Test handling of general OpenAI API errors."""
    policy = SendBackendRequestPolicy()
    db_session = AsyncMock(spec=AsyncSession)

    # Configure client to raise API error
    mock_request = httpx.Request("POST", "https://api.test-backend.com/chat/completions")
    api_error = openai.APIError("Invalid request", request=mock_request, body=None)
    mock_openai_client.chat.completions.create.side_effect = api_error

    with caplog.at_level(logging.ERROR):
        with pytest.raises(openai.APIError, match="Invalid request"):
            await policy.apply(sample_transaction, test_container, db_session)

    assert "OpenAI API error during backend request" in caplog.text


@pytest.mark.asyncio
async def test_send_backend_request_policy_unexpected_error(
    sample_transaction: Transaction,
    test_container: MagicMock,
    mock_openai_client: AsyncMock,
    caplog,
):
    """Test handling of unexpected errors during backend request."""
    policy = SendBackendRequestPolicy()
    db_session = AsyncMock(spec=AsyncSession)

    # Configure client to raise unexpected error
    unexpected_error = RuntimeError("Something went wrong")
    mock_openai_client.chat.completions.create.side_effect = unexpected_error

    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError, match="Something went wrong"):
            await policy.apply(sample_transaction, test_container, db_session)

    assert "Unexpected error during backend request" in caplog.text


@pytest.mark.asyncio
async def test_send_backend_request_policy_filters_none_values(
    sample_transaction: Transaction,
    test_container: MagicMock,
    mock_openai_client: AsyncMock,
):
    """Test that None values are filtered from request payload."""
    policy = SendBackendRequestPolicy()
    db_session = AsyncMock(spec=AsyncSession)

    # Add some None values to the request payload
    assert sample_transaction.openai_request is not None
    assert sample_transaction.openai_request.payload is not None
    sample_transaction.openai_request.payload.stream = None
    sample_transaction.openai_request.payload.stop = None

    await policy.apply(sample_transaction, test_container, db_session)

    call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs

    # None values should be filtered out
    assert "stream" not in call_kwargs
    assert "stop" not in call_kwargs
    # Non-None values should be present
    assert "model" in call_kwargs
    assert "messages" in call_kwargs


@pytest.mark.asyncio
async def test_send_backend_request_policy_different_model(
    test_container: MagicMock,
    mock_openai_client: AsyncMock,
):
    """Test with a different model in the request."""
    # Create transaction with different model
    transaction = Transaction(
        openai_request=create_chat_request(
            model="gpt-3.5-turbo",
            messages=[Message(role="user", content="Test message")],
        ),
        openai_response=create_chat_response(model="gpt-3.5-turbo", prompt_tokens=5, completion_tokens=3),
        data=EventedDict(),
    )
    db_session = AsyncMock(spec=AsyncSession)

    policy = SendBackendRequestPolicy()
    await policy.apply(transaction, test_container, db_session)

    call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-3.5-turbo"
    assert len(call_kwargs["messages"]) == 1


def test_send_backend_request_policy_serialize_default():
    """Test serialization with default name."""
    policy = SendBackendRequestPolicy()

    serialized = policy.serialize()

    assert serialized["type"] == "SendBackendRequest"
    assert "name" in serialized  # Now includes default class name


def test_send_backend_request_policy_serialize_custom():
    """Test serialization with custom name."""
    custom_name = "CustomBackendPolicy"
    policy = SendBackendRequestPolicy(name=custom_name)

    serialized = policy.serialize()

    assert serialized["type"] == "SendBackendRequest"
    assert serialized["name"] == custom_name


def test_send_backend_request_policy_from_serialized_with_name():
    """Test deserialization with name in config."""
    config = cast(SerializableDict, {"name": "DeserializedPolicy"})

    policy = SendBackendRequestPolicy.from_serialized(config)

    assert policy.name == "DeserializedPolicy"


def test_send_backend_request_policy_from_serialized_without_name():
    """Test deserialization without name in config."""
    config = {}

    policy = SendBackendRequestPolicy.from_serialized(config)

    assert policy.name == "SendBackendRequestPolicy"


def test_send_backend_request_policy_from_serialized_non_string_name():
    """Test deserialization with non-string name raises ValidationError."""
    config = cast(SerializableDict, {"name": 12345})

    with pytest.raises(Exception):  # Pydantic will raise ValidationError for invalid types
        SendBackendRequestPolicy.from_serialized(config)


def test_send_backend_request_policy_round_trip_serialization():
    """Test serialization and deserialization round trip."""
    original_name = "RoundTripTestPolicy"
    original_policy = SendBackendRequestPolicy(name=original_name)

    # Serialize
    serialized = original_policy.serialize()

    # Deserialize
    restored_policy = SendBackendRequestPolicy.from_serialized(serialized)

    # Verify
    assert restored_policy.name == original_policy.name
    assert restored_policy.serialize() == original_policy.serialize()


@pytest.mark.parametrize(
    "name,expected",
    [
        (None, "SendBackendRequestPolicy"),  # Default name (now returns class name)
        ("CustomPolicy", "CustomPolicy"),  # Custom name
        ("Policy123", "Policy123"),  # Alphanumeric name
        ("", ""),  # Empty string
    ],
)
def test_send_backend_request_policy_parametrized_initialization(name: str | None, expected: str):
    """Test initialization with various name parameters."""
    policy = SendBackendRequestPolicy() if name is None else SendBackendRequestPolicy(name=name)
    assert policy.name == expected


@pytest.mark.asyncio
async def test_send_backend_request_policy_container_client_creation(
    sample_transaction: Transaction,
):
    """Test that the policy correctly uses container to create OpenAI client."""
    policy = SendBackendRequestPolicy()
    db_session = AsyncMock(spec=AsyncSession)

    # Create a minimal container with only what we need
    container = MagicMock(spec=DependencyContainer)

    # Create a test client
    test_client = AsyncMock()
    test_response = MagicMock()
    test_response.model_dump.return_value = create_mock_openai_response(id="test-response", content="Test")
    test_client.chat.completions.create.return_value = test_response

    container.create_openai_client.return_value = test_client

    await policy.apply(sample_transaction, container, db_session)

    # Verify that create_openai_client was called with the correct parameters from transaction.request
    container.create_openai_client.assert_called_once_with("https://api.openai.com/chat/completions", "test_key")

    # Verify that the returned client was used
    test_client.chat.completions.create.assert_called_once()


@pytest.mark.asyncio
async def test_send_backend_request_policy_debug_info_with_response(
    sample_transaction: Transaction,
    test_container: MagicMock,
    mock_openai_client: AsyncMock,
):
    """Test debug info creation with OpenAI error that has response details."""
    policy = SendBackendRequestPolicy()
    db_session = AsyncMock(spec=AsyncSession)

    # Create a mock response with detailed error information
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.headers = {"content-type": "application/json"}
    mock_response.text = '{"error": {"message": "Not Found"}}'

    # Create HTTPx request for OpenAI error
    mock_request = httpx.Request("POST", "https://api.openai.com/chat/completions")

    # Configure client to raise API error with detailed response
    api_error = openai.APIError("Model not found", request=mock_request, body={"error": "model_not_found"})
    # Manually add response attribute for testing
    setattr(api_error, "response", mock_response)
    mock_openai_client.chat.completions.create.side_effect = api_error

    with pytest.raises(openai.APIError) as exc_info:
        await policy.apply(sample_transaction, test_container, db_session)

    # Verify debug info was attached
    caught_error = exc_info.value
    assert hasattr(caught_error, "debug_info")
    debug_info = getattr(caught_error, "debug_info")
    assert debug_info["backend_url"] == "https://api.openai.com/chat/completions"
    assert debug_info["request_model"] == "gpt-4"
    assert debug_info["request_messages_count"] == 2
    assert debug_info["error_type"] == "APIError"
    assert debug_info["backend_response"]["status_code"] == 404
    assert debug_info["backend_response"]["headers"]["content-type"] == "application/json"
    assert debug_info["backend_response"]["body"] == '{"error": {"message": "Not Found"}}'
    assert debug_info["backend_error_body"] == {"error": "model_not_found"}
    assert debug_info["api_key_identifier"] == "test...ey"


def test_get_api_key_identifier():
    """Test API key identifier generation for different key lengths."""
    policy = SendBackendRequestPolicy()

    # Test empty key
    assert policy._get_api_key_identifier("") == "empty"

    # Test short key (<=12 chars)
    assert policy._get_api_key_identifier("short") == "shor...rt"
    assert policy._get_api_key_identifier("key12345678") == "key1...78"

    # Test normal key (>12 chars)
    assert policy._get_api_key_identifier("sk-1234567890abcdefghijk") == "sk-12345...hijk"

    # Test very long key
    long_key = "sk-" + "x" * 50
    result = policy._get_api_key_identifier(long_key)
    assert result.startswith("sk-xxxxx")
    assert result.endswith("xxxx")
    assert "..." in result


@pytest.mark.asyncio
async def test_send_backend_request_policy_create_debug_info_no_response():
    """Test debug info creation without response details."""
    policy = SendBackendRequestPolicy()

    # Create a simple error without response
    error = RuntimeError("Connection failed")
    request_payload = MagicMock()
    request_payload.model = "gpt-4"
    request_payload.messages = ["msg1", "msg2"]

    debug_info = policy._create_debug_info("https://api.test.com", request_payload, error, "test-api-key")

    assert debug_info["backend_url"] == "https://api.test.com"
    assert debug_info["request_model"] == "gpt-4"
    assert debug_info["request_messages_count"] == 2
    assert debug_info["error_type"] == "RuntimeError"
    assert debug_info["error_message"] == "Connection failed"
    assert "backend_response" not in debug_info
    assert "backend_error_body" not in debug_info


@pytest.mark.asyncio
async def test_send_backend_request_policy_raw_request():
    """Test handling of raw HTTP requests."""
    policy = SendBackendRequestPolicy()

    # Create a transaction with raw request
    raw_request = RawRequest(
        method="POST",
        path="v1/models",
        headers={"content-type": "application/json"},
        body=b'{"test": "data"}',
        api_key="test-api-key",
        backend_url="https://api.test-backend.com",
    )
    transaction = Transaction(raw_request=raw_request)

    container = MagicMock(spec=DependencyContainer)
    db_session = AsyncMock(spec=AsyncSession)

    # Mock httpx response
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {"content-type": "application/json"}
        mock_response.content = b'{"models": []}'
        mock_response.text = '{"models": []}'
        mock_client.request.return_value = mock_response

        result = await policy.apply(transaction, container, db_session)

        # Verify request was made correctly
        mock_client.request.assert_called_once_with(
            method="POST",
            url="https://api.test-backend.com/v1/models",
            headers={"content-type": "application/json", "Authorization": "Bearer test-api-key"},
            content=b'{"test": "data"}',
        )

        # Verify response was stored
        assert result.raw_response is not None
        assert result.raw_response.status_code == 200
        assert result.raw_response.headers == {"content-type": "application/json"}
        assert result.raw_response.body == b'{"models": []}'
        assert result.raw_response.content == '{"models": []}'


@pytest.mark.asyncio
async def test_send_backend_request_policy_raw_request_no_backend_url():
    """Test raw request with fallback backend URL."""
    policy = SendBackendRequestPolicy()

    # Create a transaction with raw request but no backend_url
    raw_request = RawRequest(
        method="GET",
        path="health",
        headers={},
        body=b"",
        api_key="test-key",
        # backend_url is None
    )
    transaction = Transaction(raw_request=raw_request)

    container = MagicMock(spec=DependencyContainer)
    db_session = AsyncMock(spec=AsyncSession)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b"OK"
        mock_response.text = "OK"
        mock_client.request.return_value = mock_response

        await policy.apply(transaction, container, db_session)

        # Should use fallback URL
        mock_client.request.assert_called_once_with(
            method="GET", url="http://localhost:8000/health", headers={"Authorization": "Bearer test-key"}, content=b""
        )


@pytest.mark.asyncio
async def test_send_backend_request_policy_raw_request_no_api_key():
    """Test raw request without API key."""
    policy = SendBackendRequestPolicy()

    # Create a transaction with raw request but no API key
    raw_request = RawRequest(
        method="GET",
        path="public",
        headers={"user-agent": "test"},
        body=b"",
        api_key="",
        backend_url="https://api.test.com",
    )
    transaction = Transaction(raw_request=raw_request)

    container = MagicMock(spec=DependencyContainer)
    db_session = AsyncMock(spec=AsyncSession)

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {}
        mock_response.content = b"public data"
        mock_response.text = None
        mock_client.request.return_value = mock_response

        result = await policy.apply(transaction, container, db_session)

        # Should not include Authorization header
        mock_client.request.assert_called_once_with(
            method="GET", url="https://api.test.com/public", headers={"user-agent": "test"}, content=b""
        )

        # Verify response with no text content
        assert result.raw_response is not None
        assert result.raw_response.content is None
        assert result.raw_response.body == b"public data"


@pytest.mark.asyncio
async def test_send_backend_request_policy_raw_request_httpx_errors():
    """Test raw request with httpx errors."""
    policy = SendBackendRequestPolicy()

    raw_request = RawRequest(
        method="POST", path="test", headers={}, body=b"data", api_key="key", backend_url="https://timeout.test.com"
    )
    transaction = Transaction(raw_request=raw_request)

    container = MagicMock(spec=DependencyContainer)
    db_session = AsyncMock(spec=AsyncSession)

    # Test timeout error
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client.request.side_effect = httpx.TimeoutException("Request timeout")

        with pytest.raises(httpx.TimeoutException):
            await policy.apply(transaction, container, db_session)

    # Test connection error
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client.request.side_effect = httpx.ConnectError("Connection failed")

        with pytest.raises(httpx.ConnectError):
            await policy.apply(transaction, container, db_session)


@pytest.mark.asyncio
async def test_send_backend_request_policy_none_openai_request():
    """Test handling of transaction with None openai_request by directly calling _handle_openai_request."""
    policy = SendBackendRequestPolicy()

    # Create transaction with None openai_request
    transaction = Transaction(openai_request=create_chat_request())
    transaction.openai_request = None

    container = MagicMock(spec=DependencyContainer)

    with pytest.raises(ValueError, match="OpenAI request is None"):
        await policy._handle_openai_request(transaction, container)


@pytest.mark.asyncio
async def test_send_backend_request_policy_none_raw_request():
    """Test handling of transaction with None raw_request by directly calling _handle_raw_request."""
    policy = SendBackendRequestPolicy()

    # Create transaction with None raw_request
    raw_request = RawRequest(method="GET", path="test", headers={}, body=b"", api_key="key")
    transaction = Transaction(raw_request=raw_request)
    transaction.raw_request = None

    container = MagicMock(spec=DependencyContainer)

    with pytest.raises(ValueError, match="Raw request is None"):
        await policy._handle_raw_request(transaction, container)


@pytest.mark.asyncio
async def test_send_backend_request_policy_creates_response_when_none():
    """Test that policy creates openai_response when it's None."""
    policy = SendBackendRequestPolicy()

    # Create transaction with no response
    transaction = Transaction(
        openai_request=create_chat_request(),
        openai_response=None,  # No response initially
        data=EventedDict(),
    )

    container = MagicMock(spec=DependencyContainer)
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.model_dump.return_value = create_mock_openai_response()
    mock_client.chat.completions.create.return_value = mock_response
    container.create_openai_client.return_value = mock_client

    db_session = AsyncMock(spec=AsyncSession)

    result = await policy.apply(transaction, container, db_session)

    # Verify response was created
    assert result.openai_response is not None
    assert result.openai_response.payload is not None


@pytest.mark.asyncio
async def test_send_backend_request_policy_invalid_request_type():
    """Test handling of transactions with invalid request type (edge case)."""
    policy = SendBackendRequestPolicy()

    # Create a valid transaction
    transaction = Transaction(openai_request=create_chat_request())

    # Patch the RequestType enum to have an additional invalid value and make the transaction return it
    from luthien_control.core import request_type

    with patch.object(request_type, "RequestType") as mock_request_type:
        # Create an enum-like object with the invalid type
        mock_request_type.OPENAI_CHAT = "OPENAI_CHAT"
        mock_request_type.RAW_PASSTHROUGH = "RAW_PASSTHROUGH"
        mock_request_type.INVALID_TYPE = "INVALID_TYPE"

        # Mock the transaction property to return the invalid type
        def mock_prop(self):
            return "INVALID_TYPE"

        with patch.object(type(transaction), "request_type", property(mock_prop)):
            container = MagicMock(spec=DependencyContainer)
            db_session = AsyncMock(spec=AsyncSession)

            with pytest.raises(ValueError, match="Transaction has no request to process"):
                await policy.apply(transaction, container, db_session)


@pytest.mark.asyncio
async def test_send_backend_request_policy_raw_request_unexpected_error():
    """Test raw request with unexpected error (not httpx specific)."""
    policy = SendBackendRequestPolicy()

    raw_request = RawRequest(
        method="POST", path="test", headers={}, body=b"data", api_key="key", backend_url="https://error.test.com"
    )
    transaction = Transaction(raw_request=raw_request)

    container = MagicMock(spec=DependencyContainer)
    db_session = AsyncMock(spec=AsyncSession)

    # Test unexpected error (not httpx specific)
    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client.request.side_effect = RuntimeError("Unexpected error")

        with pytest.raises(RuntimeError, match="Unexpected error"):
            await policy.apply(transaction, container, db_session)
