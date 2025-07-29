import os
from typing import Any, Dict, Optional, cast
from unittest.mock import AsyncMock, MagicMock

import httpx
import openai
import pytest
from luthien_control.api.openai_chat_completions.datatypes import (
    Message,
    ResponseFormat,
    Usage,
)
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse
from luthien_control.control_policy.backend_call_policy import BackendCallPolicy
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.request import Request
from luthien_control.core.response import Response
from luthien_control.core.transaction import Transaction
from luthien_control.utils.backend_call_spec import BackendCallSpec
from psygnal.containers import EventedList

EXAMPLE_API_ENDPOINT = "https://api.example.com"


@pytest.fixture
def mock_openai_response():
    """Standard OpenAI response for testing."""
    return OpenAIChatCompletionsResponse(
        id="chatcmpl-123",
        object="chat.completion",
        created=1677652288,
        model="gpt-4o",
        choices=EventedList([]),
        usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


@pytest.fixture
def base_transaction():
    """Base transaction for testing."""
    payload = OpenAIChatCompletionsRequest(
        model="gpt-3.5-turbo",
        messages=EventedList([Message(role="user", content="Hello")]),
    )
    request = Request(
        payload=payload,
        api_endpoint="https://default.com/",
        api_key="default-key",
    )
    return Transaction(openai_request=request, openai_response=Response())


@pytest.fixture
def mock_container_and_client(mock_openai_response):
    """Mock container with OpenAI client that returns standard response."""
    mock_openai_client = AsyncMock()
    mock_openai_client.chat.completions.create.return_value = mock_openai_response

    container = MagicMock(spec=DependencyContainer)
    container.create_openai_client.return_value = mock_openai_client

    return container, mock_openai_client


async def apply_policy_and_verify_basics(
    policy: BackendCallPolicy,
    transaction: Transaction,
    container: MagicMock,
    mock_openai_client: AsyncMock,
    expected_api_key: str,
    expected_endpoint: str = EXAMPLE_API_ENDPOINT,
) -> Transaction:
    """Apply policy and verify basic API call setup."""
    session = AsyncMock()
    result = await policy.apply(transaction, container, session)

    # Verify basic request configuration
    assert result.openai_request is not None
    assert result.openai_request.api_endpoint == expected_endpoint

    # Verify OpenAI client creation and API call
    container.create_openai_client.assert_called_once_with(expected_endpoint, expected_api_key)
    mock_openai_client.chat.completions.create.assert_called_once()

    return result


def create_backend_call_spec(
    request_args: Optional[Dict[str, Any]] = None, api_key_env_var: str = "TEST_API_KEY"
) -> BackendCallSpec:
    """Create a BackendCallSpec with common defaults."""
    return BackendCallSpec(
        model="gpt-4o",
        api_endpoint=EXAMPLE_API_ENDPOINT,
        api_key_env_var=api_key_env_var,
        request_args=request_args or {},
    )


def setup_api_key_env(api_key: Optional[str] = "test-key-123", env_var: str = "TEST_API_KEY"):
    """Setup or remove API key environment variable."""
    if api_key:
        os.environ[env_var] = api_key
    else:
        os.environ.pop(env_var, None)


def create_openai_exception(exception_class, message: str = "Test error"):
    """Create OpenAI exception with proper httpx.Request."""
    mock_request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    if exception_class == openai.APITimeoutError:
        return exception_class(request=mock_request)
    elif exception_class == openai.APIConnectionError:
        return exception_class(message=message, request=mock_request)
    elif exception_class == openai.APIError:
        return exception_class(message=message, request=mock_request, body=None)
    else:
        return exception_class(message)


@pytest.mark.asyncio
async def test_backend_call_policy_basic(base_transaction, mock_container_and_client, mock_openai_response):
    """Test basic functionality of BackendCallPolicy."""
    setup_api_key_env()

    spec = create_backend_call_spec(
        {
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 0.9,
        }
    )
    policy = BackendCallPolicy(backend_call_spec=spec, name="test_policy")
    container, mock_openai_client = mock_container_and_client

    result = await apply_policy_and_verify_basics(
        policy, base_transaction, container, mock_openai_client, "test-key-123"
    )

    # Verify request arguments were applied
    assert result.openai_request is not None
    assert result.openai_request.api_key == "test-key-123"
    assert result.openai_request.payload is not None
    assert result.openai_request.payload.model == "gpt-4o"
    assert result.openai_request.payload.temperature == 0.7
    assert result.openai_request.payload.max_tokens == 1000
    assert result.openai_request.payload.top_p == 0.9

    # Verify response was set
    assert result.openai_response is not None
    assert result.openai_response is not None
    assert result.openai_response.payload == mock_openai_response
    assert result.openai_response.api_endpoint == EXAMPLE_API_ENDPOINT


@pytest.mark.asyncio
async def test_backend_call_policy_nested_objects(base_transaction, mock_container_and_client, mock_openai_response):
    """Test BackendCallPolicy with nested pydantic objects."""
    setup_api_key_env()

    spec = create_backend_call_spec({"response_format": {"type": "json_object"}})
    policy = BackendCallPolicy(backend_call_spec=spec, name="test_policy")
    container, mock_openai_client = mock_container_and_client

    result = await apply_policy_and_verify_basics(
        policy, base_transaction, container, mock_openai_client, "test-key-123"
    )

    # Verify nested object was properly converted
    assert result.openai_request is not None
    assert result.openai_request.payload is not None
    assert result.openai_request.payload.response_format is not None
    assert isinstance(result.openai_request.payload.response_format, ResponseFormat)
    assert result.openai_request.payload.response_format.type == "json_object"
    assert result.openai_response is not None
    assert result.openai_response.payload == mock_openai_response


@pytest.mark.asyncio
async def test_backend_call_policy_complex_nested_objects(mock_container_and_client, mock_openai_response):
    """Test BackendCallPolicy with complex nested pydantic objects."""
    setup_api_key_env()

    # Create transaction with different message for this test
    payload = OpenAIChatCompletionsRequest(
        model="gpt-3.5-turbo",
        messages=EventedList([Message(role="user", content="What's the weather?")]),
    )
    transaction = Transaction(
        openai_request=Request(payload=payload, api_endpoint="https://default.com", api_key="default-key"),
        openai_response=Response(),
    )

    # Complex nested request args
    complex_args = {
        "response_format": {"type": "json_object"},
        "web_search_options": {
            "search_context_size": "large",
            "user_location": {
                "type": "approximate",
                "approximate": {
                    "city": "San Francisco",
                    "country": "USA",
                    "region": "CA",
                    "timezone": "America/Los_Angeles",
                },
            },
        },
        "tool_choice": {"type": "function", "function": {"name": "get_weather"}},
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get the current weather",
                    "parameters": {"type": "object", "properties": {"location": {"type": "string"}}},
                },
            }
        ],
    }

    spec = create_backend_call_spec(complex_args)
    policy = BackendCallPolicy(backend_call_spec=spec, name="test_policy")
    container, mock_openai_client = mock_container_and_client

    result = await apply_policy_and_verify_basics(policy, transaction, container, mock_openai_client, "test-key-123")

    # Verify deeply nested structures
    assert result.openai_request is not None
    assert result.openai_request.payload is not None
    payload = cast(OpenAIChatCompletionsRequest, result.openai_request.payload)
    assert payload.response_format is not None
    assert payload.response_format.type == "json_object"

    assert payload.web_search_options is not None
    web_search = payload.web_search_options
    assert web_search.search_context_size == "large"
    assert web_search.user_location is not None
    assert web_search.user_location.type == "approximate"
    assert web_search.user_location.approximate is not None
    assert web_search.user_location.approximate.city == "San Francisco"
    assert web_search.user_location.approximate.country == "USA"

    assert payload.tool_choice is not None
    assert payload.tool_choice.type == "function"
    assert payload.tool_choice.function is not None
    assert payload.tool_choice.function.name == "get_weather"

    assert payload.tools is not None
    assert len(payload.tools) == 1
    assert payload.tools[0].function.name == "get_weather"
    assert payload.tools[0].function.description == "Get the current weather"

    assert result.openai_response is not None
    assert result.openai_response.payload == mock_openai_response


@pytest.mark.asyncio
async def test_backend_call_policy_no_api_key(base_transaction, mock_container_and_client, mock_openai_response):
    """Test BackendCallPolicy when API key env var is not set."""
    setup_api_key_env(None, "MISSING_API_KEY")  # Remove the env var

    spec = create_backend_call_spec({}, "MISSING_API_KEY")
    policy = BackendCallPolicy(backend_call_spec=spec, name="test_policy")
    container, mock_openai_client = mock_container_and_client

    result = await apply_policy_and_verify_basics(
        policy,
        base_transaction,
        container,
        mock_openai_client,
        "default-key",  # Falls back to transaction key
    )

    # API key should remain unchanged if env var is not set
    assert result.openai_request is not None
    assert result.openai_request.api_key == "default-key"
    assert result.openai_response is not None
    assert result.openai_response.payload == mock_openai_response


@pytest.mark.asyncio
async def test_backend_call_policy_openai_api_timeout(base_transaction, mock_container_and_client):
    """Test BackendCallPolicy handles OpenAI API timeout errors."""
    setup_api_key_env()

    spec = create_backend_call_spec()
    policy = BackendCallPolicy(backend_call_spec=spec, name="test_policy")
    container, mock_openai_client = mock_container_and_client

    # Configure client to raise timeout error
    mock_openai_client.chat.completions.create.side_effect = create_openai_exception(openai.APITimeoutError)

    session = AsyncMock()

    # Verify that the timeout error is propagated
    with pytest.raises(openai.APITimeoutError):
        await policy.apply(base_transaction, container, session)


@pytest.mark.asyncio
async def test_backend_call_policy_openai_api_connection_error(base_transaction, mock_container_and_client):
    """Test BackendCallPolicy handles OpenAI API connection errors."""
    setup_api_key_env()

    spec = create_backend_call_spec()
    policy = BackendCallPolicy(backend_call_spec=spec, name="test_policy")
    container, mock_openai_client = mock_container_and_client

    # Configure client to raise connection error
    mock_openai_client.chat.completions.create.side_effect = create_openai_exception(
        openai.APIConnectionError, "Connection failed"
    )

    session = AsyncMock()

    # Verify that the connection error is propagated
    with pytest.raises(openai.APIConnectionError):
        await policy.apply(base_transaction, container, session)


@pytest.mark.asyncio
async def test_backend_call_policy_openai_api_error(base_transaction, mock_container_and_client):
    """Test BackendCallPolicy handles generic OpenAI API errors."""
    setup_api_key_env()

    spec = create_backend_call_spec()
    policy = BackendCallPolicy(backend_call_spec=spec, name="test_policy")
    container, mock_openai_client = mock_container_and_client

    # Configure client to raise generic API error
    mock_openai_client.chat.completions.create.side_effect = create_openai_exception(
        openai.APIError, "API error occurred"
    )

    session = AsyncMock()

    # Verify that the API error is propagated
    with pytest.raises(openai.APIError):
        await policy.apply(base_transaction, container, session)


@pytest.mark.asyncio
async def test_backend_call_policy_unexpected_exception(base_transaction, mock_container_and_client):
    """Test BackendCallPolicy handles unexpected exceptions."""
    setup_api_key_env()

    spec = create_backend_call_spec()
    policy = BackendCallPolicy(backend_call_spec=spec, name="test_policy")
    container, mock_openai_client = mock_container_and_client

    # Configure client to raise unexpected error
    mock_openai_client.chat.completions.create.side_effect = RuntimeError("Unexpected error")

    session = AsyncMock()

    # Verify that the unexpected error is propagated
    with pytest.raises(RuntimeError):
        await policy.apply(base_transaction, container, session)


def test_backend_call_policy_serialization():
    """Test BackendCallPolicy serialization and deserialization."""
    spec = create_backend_call_spec({"temperature": 0.8, "max_tokens": 500})
    policy = BackendCallPolicy(backend_call_spec=spec, name="test_policy")

    # Test serialization
    serialized = policy.serialize()
    expected_keys = {"type", "name", "backend_call_spec"}
    assert set(serialized.keys()) == expected_keys
    assert serialized["type"] == "BackendCallPolicy"
    assert serialized["name"] == "test_policy"
    backend_call_spec = cast(Dict[str, Any], serialized["backend_call_spec"])
    assert backend_call_spec["model"] == "gpt-4o"
    assert backend_call_spec["api_endpoint"] == EXAMPLE_API_ENDPOINT
    request_args = cast(Dict[str, Any], backend_call_spec["request_args"])
    assert request_args["temperature"] == 0.8

    # Test deserialization
    deserialized_policy = BackendCallPolicy.from_serialized(serialized)
    assert isinstance(deserialized_policy, BackendCallPolicy)
    assert deserialized_policy.name == "test_policy"
    assert deserialized_policy.backend_call_spec.model == "gpt-4o"
    assert deserialized_policy.backend_call_spec.api_endpoint == EXAMPLE_API_ENDPOINT
    assert deserialized_policy.backend_call_spec.request_args["temperature"] == 0.8
    assert deserialized_policy.backend_call_spec.request_args["max_tokens"] == 500
