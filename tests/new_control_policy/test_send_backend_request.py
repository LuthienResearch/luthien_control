"""Tests for SendBackendRequestPolicy."""

import logging
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import httpx
import openai
import pytest
from luthien_control.api.openai_chat_completions.datatypes import Choice, Message, Usage
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.request import Request
from luthien_control.core.response import Response
from luthien_control.core.transaction import Transaction
from luthien_control.new_control_policy.exceptions import NoRequestError
from luthien_control.new_control_policy.send_backend_request import SendBackendRequestPolicy
from luthien_control.new_control_policy.serialization import SerializableDict
from psygnal.containers import EventedDict, EventedList
from sqlalchemy.ext.asyncio import AsyncSession

# --- Test Fixtures ---


@pytest.fixture
def sample_transaction() -> Transaction:
    """Provides a Transaction with OpenAI chat completions request for testing."""
    request = Request(
        payload=OpenAIChatCompletionsRequest(
            model="gpt-4",
            messages=EventedList(
                [
                    Message(role="system", content="You are a helpful assistant."),
                    Message(role="user", content="Hello, world!"),
                ]
            ),
            temperature=0.7,
            max_tokens=100,
        ),
        api_endpoint="https://api.openai.com/v1/chat/completions",
        api_key="test_key",
    )

    response = Response(
        payload=OpenAIChatCompletionsResponse(
            id="chatcmpl-123",
            object="chat.completion",
            created=1677652288,
            model="gpt-4",
            choices=EventedList(
                [Choice(index=0, message=Message(role="assistant", content="Hello there!"), finish_reason="stop")]
            ),
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
    )

    transaction_data = EventedDict(
        {
            "test_key": "test_value",
        }
    )

    return Transaction(request=request, response=response, data=transaction_data)


@pytest.fixture
def mock_settings() -> MagicMock:
    """Provides a mock Settings object."""
    settings = MagicMock()
    settings.get_backend_url.return_value = "https://api.test-backend.com/v1"
    settings.get_openai_api_key.return_value = "test-backend-api-key"
    return settings


@pytest.fixture
def mock_openai_client() -> AsyncMock:
    """Provides a mock OpenAI client."""
    client = AsyncMock()

    # Mock a successful chat completion response
    mock_response = MagicMock()
    mock_response.model_dump.return_value = {
        "id": "chatcmpl-backend-123",
        "object": "chat.completion",
        "created": 1677652388,
        "model": "gpt-4",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "Hello! How can I help you today?"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 15, "completion_tokens": 10, "total_tokens": 25},
    }

    client.chat.completions.create.return_value = mock_response
    return client


@pytest.fixture
def mock_container(mock_settings: MagicMock, mock_openai_client: AsyncMock) -> MagicMock:
    """Provides a mock dependency container."""
    container = MagicMock(spec=DependencyContainer)
    container.settings = mock_settings
    container.create_openai_client.return_value = mock_openai_client
    return container


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Provides a mock database session."""
    return AsyncMock(spec=AsyncSession)


# --- Test Cases ---


def test_send_backend_request_policy_initialization_default():
    """Test SendBackendRequestPolicy initialization with default name."""
    policy = SendBackendRequestPolicy()

    assert policy.name == "SendBackendRequestPolicy"


def test_send_backend_request_policy_initialization_custom():
    """Test SendBackendRequestPolicy initialization with custom name."""
    custom_name = "CustomBackendPolicy"
    policy = SendBackendRequestPolicy(name=custom_name)

    assert policy.name == custom_name


@pytest.mark.asyncio
async def test_send_backend_request_policy_no_request(
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that NoRequestError is raised when transaction has no request."""
    policy = SendBackendRequestPolicy()

    # Create a mock transaction with request=None
    mock_transaction = MagicMock(spec=Transaction)
    mock_transaction.request = None

    with pytest.raises(NoRequestError, match="No request in transaction for backend request"):
        await policy.apply(mock_transaction, mock_container, mock_db_session)


@pytest.mark.asyncio
async def test_send_backend_request_policy_no_backend_url(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that ValueError is raised when backend URL is not configured."""
    policy = SendBackendRequestPolicy()

    # Configure mock to return None for backend URL
    mock_container.settings.get_backend_url.return_value = None

    with pytest.raises(ValueError, match="Backend URL is not configured"):
        await policy.apply(sample_transaction, mock_container, mock_db_session)


@pytest.mark.asyncio
async def test_send_backend_request_policy_no_api_key(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that ValueError is raised when API key is not configured."""
    policy = SendBackendRequestPolicy()

    # Configure mock to return None for API key
    mock_container.settings.get_openai_api_key.return_value = None

    with pytest.raises(ValueError, match="OpenAI API key is not configured"):
        await policy.apply(sample_transaction, mock_container, mock_db_session)


@pytest.mark.asyncio
async def test_send_backend_request_policy_successful_request(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_openai_client: AsyncMock,
    mock_db_session: AsyncMock,
):
    """Test successful backend request and response handling."""
    policy = SendBackendRequestPolicy()

    result = await policy.apply(sample_transaction, mock_container, mock_db_session)

    assert result is sample_transaction

    # Verify OpenAI client was created with correct parameters
    mock_container.create_openai_client.assert_called_once_with(
        "https://api.test-backend.com/v1", "test-backend-api-key"
    )

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
    assert sample_transaction.response.payload.id == "chatcmpl-backend-123"
    assert sample_transaction.response.payload.model == "gpt-4"
    assert len(sample_transaction.response.payload.choices) == 1
    assert sample_transaction.response.payload.choices[0].message.content == "Hello! How can I help you today?"
    assert sample_transaction.response.payload.usage.total_tokens == 25


@pytest.mark.asyncio
async def test_send_backend_request_policy_logging(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_openai_client: AsyncMock,
    mock_db_session: AsyncMock,
    caplog,
):
    """Test that requests and responses are logged correctly."""
    policy = SendBackendRequestPolicy(name="TestPolicy")

    with caplog.at_level(logging.INFO):
        await policy.apply(sample_transaction, mock_container, mock_db_session)

    # Check request logging
    assert "Sending chat completions request to backend with model 'gpt-4' and 2 messages. (TestPolicy)" in caplog.text

    # Check response logging
    assert "Received backend response with 1 choices and usage:" in caplog.text
    assert "(TestPolicy)" in caplog.text


@pytest.mark.asyncio
async def test_send_backend_request_policy_api_timeout_error(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_openai_client: AsyncMock,
    mock_db_session: AsyncMock,
    caplog,
):
    """Test handling of OpenAI API timeout errors."""
    policy = SendBackendRequestPolicy()

    # Configure client to raise timeout error
    mock_request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    timeout_error = openai.APITimeoutError(request=mock_request)
    mock_openai_client.chat.completions.create.side_effect = timeout_error

    with caplog.at_level(logging.ERROR):
        with pytest.raises(openai.APITimeoutError):
            await policy.apply(sample_transaction, mock_container, mock_db_session)

    assert "Timeout error during backend request" in caplog.text


@pytest.mark.asyncio
async def test_send_backend_request_policy_api_connection_error(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_openai_client: AsyncMock,
    mock_db_session: AsyncMock,
    caplog,
):
    """Test handling of OpenAI API connection errors."""
    import httpx

    policy = SendBackendRequestPolicy()

    # Configure client to raise connection error
    mock_request = httpx.Request("POST", "https://api.test-backend.com/v1/chat/completions")
    connection_error = openai.APIConnectionError(message="Connection failed", request=mock_request)
    mock_openai_client.chat.completions.create.side_effect = connection_error

    with caplog.at_level(logging.ERROR):
        with pytest.raises(openai.APIConnectionError, match="Connection failed"):
            await policy.apply(sample_transaction, mock_container, mock_db_session)

    assert "Connection error during backend request" in caplog.text


@pytest.mark.asyncio
async def test_send_backend_request_policy_api_error(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_openai_client: AsyncMock,
    mock_db_session: AsyncMock,
    caplog,
):
    """Test handling of general OpenAI API errors."""
    import httpx

    policy = SendBackendRequestPolicy()

    # Configure client to raise API error
    mock_request = httpx.Request("POST", "https://api.test-backend.com/v1/chat/completions")
    api_error = openai.APIError("Invalid request", request=mock_request, body=None)
    mock_openai_client.chat.completions.create.side_effect = api_error

    with caplog.at_level(logging.ERROR):
        with pytest.raises(openai.APIError, match="Invalid request"):
            await policy.apply(sample_transaction, mock_container, mock_db_session)

    assert "OpenAI API error during backend request" in caplog.text


@pytest.mark.asyncio
async def test_send_backend_request_policy_unexpected_error(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_openai_client: AsyncMock,
    mock_db_session: AsyncMock,
    caplog,
):
    """Test handling of unexpected errors during backend request."""
    policy = SendBackendRequestPolicy()

    # Configure client to raise unexpected error
    unexpected_error = RuntimeError("Something went wrong")
    mock_openai_client.chat.completions.create.side_effect = unexpected_error

    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError, match="Something went wrong"):
            await policy.apply(sample_transaction, mock_container, mock_db_session)

    assert "Unexpected error during backend request" in caplog.text


@pytest.mark.asyncio
async def test_send_backend_request_policy_filters_none_values(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_openai_client: AsyncMock,
    mock_db_session: AsyncMock,
):
    """Test that None values are filtered from request payload."""
    policy = SendBackendRequestPolicy()

    # Add some None values to the request payload
    sample_transaction.request.payload.stream = None
    sample_transaction.request.payload.stop = None

    await policy.apply(sample_transaction, mock_container, mock_db_session)

    call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs

    # None values should be filtered out
    assert "stream" not in call_kwargs
    assert "stop" not in call_kwargs
    # Non-None values should be present
    assert "model" in call_kwargs
    assert "messages" in call_kwargs


@pytest.mark.asyncio
async def test_send_backend_request_policy_different_model(
    mock_container: MagicMock,
    mock_openai_client: AsyncMock,
    mock_db_session: AsyncMock,
):
    """Test with a different model in the request."""
    # Create transaction with different model
    request = Request(
        payload=OpenAIChatCompletionsRequest(
            model="gpt-3.5-turbo",
            messages=EventedList(
                [
                    Message(role="user", content="Test message"),
                ]
            ),
        ),
        api_endpoint="https://api.openai.com/v1/chat/completions",
        api_key="test_key",
    )

    response = Response(
        payload=OpenAIChatCompletionsResponse(
            id="chatcmpl-123",
            object="chat.completion",
            created=1677652288,
            model="gpt-3.5-turbo",
            choices=EventedList(
                [Choice(index=0, message=Message(role="assistant", content="Response"), finish_reason="stop")]
            ),
            usage=Usage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
        )
    )

    transaction = Transaction(request=request, response=response, data=EventedDict())

    policy = SendBackendRequestPolicy()

    await policy.apply(transaction, mock_container, mock_db_session)

    call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["model"] == "gpt-3.5-turbo"
    assert len(call_kwargs["messages"]) == 1


def test_send_backend_request_policy_serialize_default():
    """Test serialization with default name."""
    policy = SendBackendRequestPolicy()

    serialized = policy.serialize()

    expected = {"type": "SendBackendRequest", "name": "SendBackendRequestPolicy"}
    assert serialized == expected


def test_send_backend_request_policy_serialize_custom():
    """Test serialization with custom name."""
    custom_name = "CustomBackendPolicy"
    policy = SendBackendRequestPolicy(name=custom_name)

    serialized = policy.serialize()

    expected = {"type": "SendBackendRequest", "name": custom_name}
    assert serialized == expected


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
    """Test deserialization with non-string name (should convert to string)."""
    config = cast(SerializableDict, {"name": 12345})

    policy = SendBackendRequestPolicy.from_serialized(config)

    assert policy.name == "12345"  # Should be converted to string


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
    "name",
    [
        None,  # Default name
        "CustomPolicy",  # Custom name
        "Policy123",  # Alphanumeric name
        "",  # Empty string (will use default)
    ],
)
def test_send_backend_request_policy_parametrized_initialization(name: str):
    """Test initialization with various name parameters."""
    if name is None:
        policy = SendBackendRequestPolicy()
        expected_name = "SendBackendRequestPolicy"
    elif name == "":
        policy = SendBackendRequestPolicy(name=name)
        expected_name = "SendBackendRequestPolicy"  # Empty string should use default
    else:
        policy = SendBackendRequestPolicy(name=name)
        expected_name = name

    assert policy.name == expected_name


@pytest.mark.asyncio
async def test_send_backend_request_policy_container_client_creation(
    sample_transaction: Transaction,
    mock_settings: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that the policy correctly uses container to create OpenAI client."""
    policy = SendBackendRequestPolicy()

    # Create a real container mock that we can verify calls on
    mock_container = MagicMock(spec=DependencyContainer)
    mock_container.settings = mock_settings

    # Create a fresh mock client for this test
    test_openai_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.model_dump.return_value = {
        "id": "test-response",
        "object": "chat.completion",
        "created": 1677652388,
        "model": "gpt-4",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "Test"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    test_openai_client.chat.completions.create.return_value = mock_response
    mock_container.create_openai_client.return_value = test_openai_client

    await policy.apply(sample_transaction, mock_container, mock_db_session)

    # Verify that create_openai_client was called with the correct parameters
    mock_container.create_openai_client.assert_called_once_with(
        "https://api.test-backend.com/v1", "test-backend-api-key"
    )

    # Verify that the returned client was used
    test_openai_client.chat.completions.create.assert_called_once()
