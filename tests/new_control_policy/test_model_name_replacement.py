"""Tests for ModelNameReplacementPolicy."""

import logging
from typing import Dict, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from luthien_control.api.openai_chat_completions.datatypes import Choice, Message, Usage
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse
from luthien_control.core.request import Request
from luthien_control.core.response import Response
from luthien_control.core.transaction import Transaction
from luthien_control.new_control_policy.exceptions import NoRequestError
from luthien_control.new_control_policy.model_name_replacement import ModelNameReplacementPolicy
from luthien_control.new_control_policy.serialization import SerializableDict
from psygnal.containers import EventedDict, EventedList

# --- Test Fixtures ---


@pytest.fixture
def model_mapping() -> Dict[str, str]:
    """Provides a sample model mapping for testing."""
    return {
        "fakename": "realname",
        "gemini-2.5-pro-preview-05-06": "gpt-4o",
        "claude-3-opus-20240229": "gpt-4-turbo",
        "cursor-small": "gpt-3.5-turbo",
    }


@pytest.fixture
def sample_transaction() -> Transaction:
    """Provides a Transaction with OpenAI chat completions request for testing."""
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


# --- Test Cases ---


def test_model_name_replacement_policy_initialization_default_name():
    """Test ModelNameReplacementPolicy initialization with default name."""
    mapping = {"fake": "real"}
    policy = ModelNameReplacementPolicy(model_mapping=mapping)

    assert policy.model_mapping == mapping


def test_model_name_replacement_policy_initialization_custom_name():
    """Test ModelNameReplacementPolicy initialization with custom name."""
    mapping = {"fake": "real"}
    custom_name = "MyCustomPolicy"
    policy = ModelNameReplacementPolicy(model_mapping=mapping, name=custom_name)

    assert policy.model_mapping == mapping
    assert policy.name == custom_name


@pytest.mark.asyncio
async def test_model_name_replacement_policy_no_request(
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that NoRequestError is raised when transaction has no request."""
    policy = ModelNameReplacementPolicy(model_mapping={})

    # Create a mock transaction with request=None using MagicMock
    mock_transaction = MagicMock(spec=Transaction)
    mock_transaction.request = None

    with pytest.raises(NoRequestError, match="No request in transaction"):
        await policy.apply(mock_transaction, mock_container, mock_db_session)


@pytest.mark.asyncio
async def test_model_name_replacement_policy_no_model_attribute(
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test policy behavior when request payload has no model attribute."""
    policy = ModelNameReplacementPolicy(model_mapping={"fake": "real"})

    # Create a mock payload without model attribute
    class MockPayload:
        def __init__(self):
            self.data = "some data"

    # Create a mock transaction with a mock request that has the payload
    mock_transaction = MagicMock(spec=Transaction)
    mock_request = MagicMock()
    mock_request.payload = MockPayload()
    mock_transaction.request = mock_request

    result = await policy.apply(mock_transaction, mock_container, mock_db_session)

    assert result is mock_transaction
    # Payload should be unchanged
    assert hasattr(result.request.payload, "data")
    assert result.request.payload.data == "some data"  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_model_name_replacement_policy_model_not_in_mapping(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that model is unchanged when not in mapping."""
    policy = ModelNameReplacementPolicy(model_mapping={"fakename": "realname"})

    # The sample transaction has model="gpt-4" which is not in the mapping
    original_model = sample_transaction.request.payload.model

    result = await policy.apply(sample_transaction, mock_container, mock_db_session)

    assert result is sample_transaction
    assert result.request.payload.model == original_model  # Should be unchanged


@pytest.mark.asyncio
async def test_model_name_replacement_policy_model_in_mapping(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
    model_mapping: Dict[str, str],
):
    """Test that model is replaced when in mapping."""
    policy = ModelNameReplacementPolicy(model_mapping=model_mapping)

    # Test each mapping
    for fake_name, real_name in model_mapping.items():
        # Set the model to the fake name
        sample_transaction.request.payload.model = fake_name

        result = await policy.apply(sample_transaction, mock_container, mock_db_session)

        assert result is sample_transaction
        assert result.request.payload.model == real_name


@pytest.mark.asyncio
async def test_model_name_replacement_policy_logging(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
    caplog,
):
    """Test that model replacement is logged correctly."""
    policy = ModelNameReplacementPolicy(model_mapping={"gpt-4": "gpt-4-turbo"})

    # Set the model to match our mapping
    sample_transaction.request.payload.model = "gpt-4"

    with caplog.at_level(logging.INFO):
        await policy.apply(sample_transaction, mock_container, mock_db_session)

    assert "Replacing model name: gpt-4 -> gpt-4-turbo" in caplog.text


@pytest.mark.asyncio
async def test_model_name_replacement_policy_multiple_applications(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that policy can be applied multiple times correctly."""
    policy = ModelNameReplacementPolicy(model_mapping={"fake1": "real1", "real1": "real2"})

    # First application: fake1 -> real1
    sample_transaction.request.payload.model = "fake1"
    result1 = await policy.apply(sample_transaction, mock_container, mock_db_session)
    assert result1.request.payload.model == "real1"

    # Second application: real1 -> real2
    result2 = await policy.apply(result1, mock_container, mock_db_session)
    assert result2.request.payload.model == "real2"


@pytest.mark.asyncio
async def test_model_name_replacement_policy_empty_mapping(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test policy behavior with empty mapping."""
    policy = ModelNameReplacementPolicy(model_mapping={})

    original_model = sample_transaction.request.payload.model

    result = await policy.apply(sample_transaction, mock_container, mock_db_session)

    assert result is sample_transaction
    assert result.request.payload.model == original_model  # Should be unchanged


def test_model_name_replacement_policy_serialize_default_name():
    """Test ModelNameReplacementPolicy serialization with default name."""
    mapping = {"fake": "real"}
    policy = ModelNameReplacementPolicy(model_mapping=mapping)

    serialized = policy.serialize()

    expected = {
        "type": "ModelNameReplacement",
        "model_mapping": mapping,
    }
    assert serialized == expected


def test_model_name_replacement_policy_serialize_custom_name():
    """Test ModelNameReplacementPolicy serialization with custom name."""
    mapping = {"fake": "real"}
    custom_name = "MyCustomPolicy"
    policy = ModelNameReplacementPolicy(model_mapping=mapping, name=custom_name)

    serialized = policy.serialize()

    expected = {
        "type": "ModelNameReplacement",
        "name": custom_name,
        "model_mapping": mapping,
    }
    assert serialized == expected


def test_model_name_replacement_policy_serialize_complex_mapping():
    """Test ModelNameReplacementPolicy serialization with complex mapping."""
    mapping = {
        "gemini-2.5-pro-preview-05-06": "gpt-4o",
        "claude-3-opus-20240229": "gpt-4-turbo",
        "cursor-small": "gpt-3.5-turbo",
        "fake-model-123": "gpt-4",
    }
    policy = ModelNameReplacementPolicy(model_mapping=mapping, name="ComplexPolicy")

    serialized = policy.serialize()

    expected = {
        "type": "ModelNameReplacement",
        "name": "ComplexPolicy",
        "model_mapping": mapping,
    }
    assert serialized == expected


def test_model_name_replacement_policy_from_serialized_with_name():
    """Test ModelNameReplacementPolicy deserialization with name."""
    config = {"type": "ModelNameReplacement", "name": "TestPolicy", "model_mapping": {"fake": "real"}}

    policy = ModelNameReplacementPolicy.from_serialized(config)

    assert policy.name == "TestPolicy"
    assert policy.model_mapping == {"fake": "real"}


def test_model_name_replacement_policy_from_serialized_without_name():
    """Test ModelNameReplacementPolicy deserialization without name."""
    config = {"type": "ModelNameReplacement", "model_mapping": {"fake": "real"}}

    policy = ModelNameReplacementPolicy.from_serialized(config)

    # When name is not provided, it defaults to the class name in __init__
    assert policy.model_mapping == {"fake": "real"}


def test_model_name_replacement_policy_from_serialized_without_mapping():
    """Test ModelNameReplacementPolicy deserialization without model_mapping."""
    config = cast(SerializableDict, {"type": "ModelNameReplacement", "name": "TestPolicy"})

    policy = ModelNameReplacementPolicy.from_serialized(config)

    assert policy.name == "TestPolicy"
    assert policy.model_mapping == {}  # Should default to empty dict


def test_model_name_replacement_policy_from_serialized_empty_config():
    """Test ModelNameReplacementPolicy deserialization with minimal config."""
    config = {}

    policy = ModelNameReplacementPolicy.from_serialized(config)

    assert policy.model_mapping == {}


def test_model_name_replacement_policy_round_trip_serialization():
    """Test ModelNameReplacementPolicy serialization and deserialization round trip."""
    mapping = {
        "gemini-2.5-pro-preview-05-06": "gpt-4o",
        "claude-3-opus-20240229": "gpt-4-turbo",
    }
    original_name = "RoundTripTestPolicy"
    original_policy = ModelNameReplacementPolicy(model_mapping=mapping, name=original_name)

    # Serialize
    serialized = original_policy.serialize()

    # Deserialize
    restored_policy = ModelNameReplacementPolicy.from_serialized(serialized)

    # Verify
    assert restored_policy.name == original_policy.name
    assert restored_policy.model_mapping == original_policy.model_mapping
    assert restored_policy.serialize() == original_policy.serialize()


@pytest.mark.parametrize(
    "mapping,name",
    [
        ({}, None),
        ({"fake": "real"}, "TestPolicy"),
        ({"a": "b", "c": "d"}, "MultiMapping"),
        ({"gemini-2.5-pro-preview-05-06": "gpt-4o"}, None),
    ],
)
def test_model_name_replacement_policy_parametrized_serialization(mapping: Dict[str, str], name: str):
    """Test ModelNameReplacementPolicy serialization with various configurations."""
    policy = ModelNameReplacementPolicy(model_mapping=mapping, name=name)

    serialized = policy.serialize()

    assert serialized.get("name") == name
    assert serialized["model_mapping"] == mapping
    assert serialized["type"] == "ModelNameReplacement"

    # Test round trip
    deserialized = ModelNameReplacementPolicy.from_serialized(serialized)
    assert deserialized.name == name
    assert deserialized.model_mapping == mapping
