"""Tests for the AddApiKeyHeaderPolicy."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from luthien_control.api.openai_chat_completions.datatypes import Choice, Message, Usage
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse
from luthien_control.core.request import Request
from luthien_control.core.response import Response
from luthien_control.core.transaction import Transaction
from luthien_control.new_control_policy.add_api_key_header import AddApiKeyHeaderPolicy
from luthien_control.new_control_policy.exceptions import ApiKeyNotFoundError, NoRequestError
from psygnal.containers import EventedDict, EventedList


@pytest.fixture
def sample_transaction() -> Transaction:
    """Provides a Transaction for testing."""
    request = Request(
        payload=OpenAIChatCompletionsRequest(
            model="gpt-4",
            messages=EventedList([Message(role="user", content="Hello, world!")]),
        ),
        api_endpoint="https://api.openai.com/v1/chat/completions",
        api_key="initial_key",  # Start with an initial key that can be overwritten
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
def mock_container() -> MagicMock:
    """Provides a mock dependency container."""
    container = MagicMock()
    return container


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Provides a mock database session."""
    return AsyncMock()


@pytest.mark.asyncio
async def test_add_api_key_success(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test successfully adding the OpenAI API key to the request."""
    # Instantiate with name (optional)
    policy = AddApiKeyHeaderPolicy(name="TestPolicy")

    # Mock the container's settings to return the OpenAI key
    mock_container.settings.get_openai_api_key.return_value = "test-openai-key-123"

    result_transaction = await policy.apply(sample_transaction, container=mock_container, session=mock_db_session)

    assert result_transaction is sample_transaction
    assert result_transaction.request is not None
    assert result_transaction.request.api_key == "test-openai-key-123"

    # Check the correct specific method was called
    mock_container.settings.get_openai_api_key.assert_called_once()


@pytest.mark.asyncio
async def test_add_api_key_missing_key(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that it raises an error if the OpenAI API key is not configured."""
    policy = AddApiKeyHeaderPolicy()

    # Mock the container's settings to return None for the OpenAI key
    mock_container.settings.get_openai_api_key.return_value = None

    # Update the expected error message to match the implementation
    with pytest.raises(ApiKeyNotFoundError, match="OpenAI API key not configured"):
        await policy.apply(sample_transaction, container=mock_container, session=mock_db_session)

    # Check the specific method was called
    mock_container.settings.get_openai_api_key.assert_called_once()


@pytest.mark.asyncio
async def test_add_api_key_no_request(
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that it raises an error if the request is not found in the transaction."""
    policy = AddApiKeyHeaderPolicy()

    # Create a mock transaction with request property that returns None
    mock_transaction = MagicMock(spec=Transaction)
    mock_transaction.request = None

    with pytest.raises(NoRequestError):
        await policy.apply(mock_transaction, container=mock_container, session=mock_db_session)

    # Ensure get_openai_api_key was NOT called if no request
    mock_container.settings.get_openai_api_key.assert_not_called()


@pytest.mark.asyncio
async def test_add_api_key_overwrites_existing(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that an existing API key is overwritten."""
    # The fixture already sets "initial_key", verify it's there
    assert sample_transaction.request.api_key == "initial_key"

    policy = AddApiKeyHeaderPolicy()

    # Mock container's settings for OpenAI key
    mock_container.settings.get_openai_api_key.return_value = "new-openai-key-456"

    result_transaction = await policy.apply(sample_transaction, container=mock_container, session=mock_db_session)

    assert result_transaction is sample_transaction
    assert result_transaction.request is not None
    assert result_transaction.request.api_key == "new-openai-key-456"

    mock_container.settings.get_openai_api_key.assert_called_once()


def test_add_api_key_header_policy_serialization():
    """Test that AddApiKeyHeaderPolicy can be serialized and deserialized correctly."""
    # Arrange - Create instance
    original_policy = AddApiKeyHeaderPolicy(name="CustomPolicyName")

    # Act - Serialize
    serialized_data = original_policy.serialize()

    # Assert Serialization - Both name and type are expected
    assert isinstance(serialized_data, dict)
    expected_serialized = {
        "name": "CustomPolicyName",
        "type": "AddApiKeyHeader",
    }
    assert serialized_data == expected_serialized

    # Act - Deserialize
    rehydrated_policy = AddApiKeyHeaderPolicy.from_serialized(config=serialized_data)

    # Assert Deserialization - Name is restored
    assert isinstance(rehydrated_policy, AddApiKeyHeaderPolicy)
    assert rehydrated_policy.name == "CustomPolicyName"


def test_add_api_key_serialization_defaults():
    """Test serialization when using default name."""
    policy = AddApiKeyHeaderPolicy()

    serialized = policy.serialize()
    # Both default name and type are expected
    assert serialized == {"name": "AddApiKeyHeaderPolicy", "type": "AddApiKeyHeader"}

    rehydrated = AddApiKeyHeaderPolicy.from_serialized(serialized)
    assert rehydrated.name == "AddApiKeyHeaderPolicy"
