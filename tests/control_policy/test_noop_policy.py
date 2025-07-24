"""Tests for the NoopPolicy."""

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from luthien_control.api.openai_chat_completions.datatypes import Choice, Message, Usage
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse
from luthien_control.control_policy.noop_policy import NoopPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.request import Request
from luthien_control.core.response import Response
from luthien_control.core.transaction import Transaction
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
def mock_container() -> MagicMock:
    """Provides a mock dependency container."""
    return MagicMock()


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Provides a mock database session."""
    return AsyncMock()


def test_noop_policy_initialization_default_name():
    """Test NoopPolicy initialization with no args."""
    _ = NoopPolicy()


def test_noop_policy_initialization_custom_name():
    """Test NoopPolicy initialization with custom name."""
    custom_name = "MyCustomNoopPolicy"
    policy = NoopPolicy(name=custom_name)
    assert policy.name == custom_name


@pytest.mark.asyncio
async def test_noop_policy_apply_does_nothing(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that NoopPolicy.apply returns the transaction unchanged."""
    policy = NoopPolicy()

    # Store original transaction state for comparison
    original_request = sample_transaction.request
    original_response = sample_transaction.response
    assert sample_transaction.data is not None
    original_data = dict(sample_transaction.data)

    result_transaction = await policy.apply(sample_transaction, mock_container, mock_db_session)

    # Verify the transaction is returned unchanged
    assert result_transaction is sample_transaction
    assert result_transaction.request is original_request
    assert result_transaction.response is original_response
    assert result_transaction.data is not None
    assert dict(result_transaction.data) == original_data

    # Verify no methods were called on mocks
    mock_container.assert_not_called()
    mock_db_session.assert_not_called()


def test_noop_policy_serialization_default_name():
    """Test NoopPolicy serialization with default name."""
    policy = NoopPolicy()
    serialized = policy.serialize()

    assert serialized["type"] == "NoopPolicy"
    assert "name" in serialized  # Pydantic includes default name


def test_noop_policy_serialization_custom_name():
    """Test NoopPolicy serialization with custom name."""
    custom_name = "MyCustomPolicy"
    policy = NoopPolicy(name=custom_name)
    serialized = policy.serialize()

    assert serialized["type"] == "NoopPolicy"
    assert serialized["name"] == custom_name


def test_noop_policy_from_serialized_with_name():
    """Test NoopPolicy.from_serialized with name in config."""
    config = cast(SerializableDict, {"name": "DeserializedPolicy"})
    policy = NoopPolicy.from_serialized(config)

    assert isinstance(policy, NoopPolicy)
    assert policy.name == "DeserializedPolicy"


def test_noop_policy_from_serialized_with_non_string_name():
    """Test NoopPolicy.from_serialized with non-string name raises ValidationError."""
    config = cast(SerializableDict, {"name": 12345})
    with pytest.raises(Exception):  # Pydantic will raise ValidationError for invalid types
        NoopPolicy.from_serialized(config)


def test_noop_policy_round_trip_serialization():
    """Test that NoopPolicy can be serialized and deserialized maintaining state."""
    original_name = "RoundTripTestPolicy"
    original_policy = NoopPolicy(name=original_name)

    # Serialize
    serialized = original_policy.serialize()

    # Deserialize
    restored_policy = NoopPolicy.from_serialized(serialized)

    # Verify
    assert restored_policy.name == original_policy.name
    assert restored_policy.serialize() == original_policy.serialize()
