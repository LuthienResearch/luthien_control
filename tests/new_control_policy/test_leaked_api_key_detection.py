"""Tests for LeakedApiKeyDetectionPolicy."""

import logging
from typing import List, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from luthien_control.api.openai_chat_completions.datatypes import Choice, Message, Usage
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse
from luthien_control.core.request import Request
from luthien_control.core.response import Response
from luthien_control.core.transaction import Transaction
from luthien_control.new_control_policy.exceptions import LeakedApiKeyError, NoRequestError
from luthien_control.new_control_policy.leaked_api_key_detection import LeakedApiKeyDetectionPolicy
from luthien_control.new_control_policy.serialization import SerializableDict
from psygnal.containers import EventedDict, EventedList

# --- Test Fixtures ---


@pytest.fixture
def sample_transaction() -> Transaction:
    """Provides a Transaction with clean message content for testing."""
    request = Request(
        payload=OpenAIChatCompletionsRequest(
            model="gpt-4",
            messages=EventedList(
                [
                    Message(role="system", content="You are a helpful assistant."),
                    Message(role="user", content="What is the square root of 64?"),
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
            model="gpt-4",
            choices=EventedList(
                [
                    Choice(
                        index=0,
                        message=Message(role="assistant", content="The square root of 64 is 8."),
                        finish_reason="stop",
                    )
                ]
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
def transaction_with_leaked_openai_key() -> Transaction:
    """Provides a Transaction with a leaked OpenAI API key in message content."""
    request = Request(
        payload=OpenAIChatCompletionsRequest(
            model="gpt-4",
            messages=EventedList(
                [
                    Message(role="system", content="You are a helpful assistant."),
                    Message(
                        role="user",
                        content=(
                            "My API key is sk-abcdefghijklmnopqrstuvwxyz1234567890abcdefghijklmn. "
                            "Can you help me use it?"
                        ),
                    ),
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
            model="gpt-4",
            choices=EventedList(
                [Choice(index=0, message=Message(role="assistant", content="Hello there!"), finish_reason="stop")]
            ),
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
    )

    return Transaction(request=request, response=response, data=EventedDict())


@pytest.fixture
def transaction_with_leaked_slack_token() -> Transaction:
    """Provides a Transaction with a leaked Slack bot token in system message."""
    request = Request(
        payload=OpenAIChatCompletionsRequest(
            model="gpt-4",
            messages=EventedList(
                [
                    Message(
                        role="system",
                        content=(
                            "You are a helpful assistant. Use this key: "
                            "xoxb-1234567890123-1234567890123-AbCdEfGhIjKlMnOpQrStUvWx for authentication."
                        ),
                    ),
                    Message(role="user", content="Hello, can you help me?"),
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
            model="gpt-4",
            choices=EventedList(
                [Choice(index=0, message=Message(role="assistant", content="Hello there!"), finish_reason="stop")]
            ),
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
    )

    return Transaction(request=request, response=response, data=EventedDict())


@pytest.fixture
def mock_container() -> MagicMock:
    """Provides a mock dependency container."""
    return MagicMock()


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Provides a mock database session."""
    return AsyncMock()


# --- Test Cases ---


def test_leaked_api_key_detection_policy_initialization_default():
    """Test LeakedApiKeyDetectionPolicy initialization with defaults."""
    policy = LeakedApiKeyDetectionPolicy()

    assert policy.name == "LeakedApiKeyDetectionPolicy"
    assert policy.patterns == LeakedApiKeyDetectionPolicy.DEFAULT_PATTERNS
    assert len(policy.compiled_patterns) == len(policy.patterns)

    # Check that patterns are compiled correctly
    for i, pattern in enumerate(policy.patterns):
        assert policy.compiled_patterns[i].pattern == pattern


def test_leaked_api_key_detection_policy_initialization_custom():
    """Test LeakedApiKeyDetectionPolicy initialization with custom values."""
    custom_patterns = ["custom-[0-9]+", "secret-[a-zA-Z0-9]{10}"]
    custom_name = "CustomDetector"

    policy = LeakedApiKeyDetectionPolicy(patterns=custom_patterns, name=custom_name)

    assert policy.name == custom_name
    assert policy.patterns == custom_patterns
    assert len(policy.compiled_patterns) == len(custom_patterns)

    # Check that custom patterns are compiled correctly
    for i, pattern in enumerate(custom_patterns):
        assert policy.compiled_patterns[i].pattern == pattern


def test_leaked_api_key_detection_policy_initialization_empty_patterns():
    """Test LeakedApiKeyDetectionPolicy initialization with empty patterns falls back to defaults."""
    # Empty list should fallback to default patterns due to 'patterns or self.DEFAULT_PATTERNS'
    policy = LeakedApiKeyDetectionPolicy(patterns=[], name="EmptyPatterns")

    assert policy.name == "EmptyPatterns"
    assert policy.patterns == LeakedApiKeyDetectionPolicy.DEFAULT_PATTERNS
    assert len(policy.compiled_patterns) == len(LeakedApiKeyDetectionPolicy.DEFAULT_PATTERNS)


def test_leaked_api_key_detection_policy_default_patterns():
    """Test that default patterns include expected API key formats."""
    expected_patterns = [
        r"sk-[a-zA-Z0-9]{48}",  # OpenAI API key pattern
        r"xoxb-[a-zA-Z0-9\-]{50,}",  # Slack bot token pattern
        r"github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}",  # GitHub PAT pattern
    ]

    assert LeakedApiKeyDetectionPolicy.DEFAULT_PATTERNS == expected_patterns


@pytest.mark.asyncio
async def test_leaked_api_key_detection_policy_no_request(
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that NoRequestError is raised when transaction has no request."""
    policy = LeakedApiKeyDetectionPolicy()

    # Create a mock transaction with request=None
    mock_transaction = MagicMock(spec=Transaction)
    mock_transaction.request = None

    with pytest.raises(NoRequestError, match="No request in transaction"):
        await policy.apply(mock_transaction, mock_container, mock_db_session)


@pytest.mark.asyncio
async def test_leaked_api_key_detection_policy_clean_messages(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that clean message content passes through without issues."""
    policy = LeakedApiKeyDetectionPolicy()

    result = await policy.apply(sample_transaction, mock_container, mock_db_session)

    assert result is sample_transaction
    # No exception should be raised


@pytest.mark.asyncio
async def test_leaked_api_key_detection_policy_no_messages_attribute(
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test policy behavior when request payload has no messages attribute."""
    policy = LeakedApiKeyDetectionPolicy()

    # Create a mock payload without messages attribute
    class MockPayload:
        def __init__(self):
            self.model = "gpt-4"

    # Create a mock transaction with a mock request that has the payload
    mock_transaction = MagicMock(spec=Transaction)
    mock_request = MagicMock()
    mock_request.payload = MockPayload()
    mock_transaction.request = mock_request

    result = await policy.apply(mock_transaction, mock_container, mock_db_session)

    assert result is mock_transaction
    # No exception should be raised


@pytest.mark.asyncio
async def test_leaked_api_key_detection_policy_detects_openai_key(
    transaction_with_leaked_openai_key: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test detection of OpenAI API key in message content."""
    policy = LeakedApiKeyDetectionPolicy()

    with pytest.raises(LeakedApiKeyError, match="Potential API key detected in message content"):
        await policy.apply(transaction_with_leaked_openai_key, mock_container, mock_db_session)


@pytest.mark.asyncio
async def test_leaked_api_key_detection_policy_detects_slack_token(
    transaction_with_leaked_slack_token: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test detection of Slack bot token in system message."""
    policy = LeakedApiKeyDetectionPolicy()

    with pytest.raises(LeakedApiKeyError, match="Potential API key detected in message content"):
        await policy.apply(transaction_with_leaked_slack_token, mock_container, mock_db_session)


@pytest.mark.asyncio
async def test_leaked_api_key_detection_policy_custom_pattern(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test detection with custom patterns."""
    # Modify the transaction to include a custom pattern
    sample_transaction.request.payload.messages[1].content = "My custom key is custom-12345. Can you help me?"

    # Use a custom pattern that matches "custom-" followed by digits
    policy = LeakedApiKeyDetectionPolicy(patterns=["custom-[0-9]+"])

    with pytest.raises(LeakedApiKeyError, match="Potential API key detected in message content"):
        await policy.apply(sample_transaction, mock_container, mock_db_session)


@pytest.mark.asyncio
async def test_leaked_api_key_detection_policy_multiple_patterns(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test detection with multiple custom patterns."""
    # Modify the transaction to include a pattern that matches the second custom pattern
    sample_transaction.request.payload.messages[1].content = "My secret is secret-abcdefghij. Can you help me?"

    # Use multiple custom patterns
    policy = LeakedApiKeyDetectionPolicy(patterns=["custom-[0-9]+", "secret-[a-zA-Z0-9]{10}"])

    with pytest.raises(LeakedApiKeyError, match="Potential API key detected in message content"):
        await policy.apply(sample_transaction, mock_container, mock_db_session)


@pytest.mark.asyncio
async def test_leaked_api_key_detection_policy_non_string_content(
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test policy behavior when message content is not a string."""
    policy = LeakedApiKeyDetectionPolicy()

    # Create a mock message with non-string content
    class MockMessage:
        def __init__(self):
            self.content = 12345  # Non-string content

    class MockPayload:
        def __init__(self):
            self.messages = [MockMessage()]

    # Create a mock transaction
    mock_transaction = MagicMock(spec=Transaction)
    mock_request = MagicMock()
    mock_request.payload = MockPayload()
    mock_transaction.request = mock_request

    result = await policy.apply(mock_transaction, mock_container, mock_db_session)

    assert result is mock_transaction
    # No exception should be raised for non-string content


@pytest.mark.asyncio
async def test_leaked_api_key_detection_policy_message_without_content(
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test policy behavior when message has no content attribute."""
    policy = LeakedApiKeyDetectionPolicy()

    # Create a mock message without content attribute
    class MockMessage:
        def __init__(self):
            self.role = "user"
            # No content attribute

    class MockPayload:
        def __init__(self):
            self.messages = [MockMessage()]

    # Create a mock transaction
    mock_transaction = MagicMock(spec=Transaction)
    mock_request = MagicMock()
    mock_request.payload = MockPayload()
    mock_transaction.request = mock_request

    result = await policy.apply(mock_transaction, mock_container, mock_db_session)

    assert result is mock_transaction
    # No exception should be raised


@pytest.mark.asyncio
async def test_leaked_api_key_detection_policy_logging(
    transaction_with_leaked_openai_key: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
    caplog,
):
    """Test that detection events are logged correctly."""
    policy = LeakedApiKeyDetectionPolicy()

    with caplog.at_level(logging.INFO):
        with pytest.raises(LeakedApiKeyError):
            await policy.apply(transaction_with_leaked_openai_key, mock_container, mock_db_session)

    # Check that the policy logged checking for keys and the warning
    assert "Checking for leaked API keys in message content" in caplog.text

    with caplog.at_level(logging.WARNING):
        with pytest.raises(LeakedApiKeyError):
            await policy.apply(transaction_with_leaked_openai_key, mock_container, mock_db_session)

    assert "Potential API key detected in message content" in caplog.text


@pytest.mark.asyncio
async def test_leaked_api_key_detection_policy_empty_patterns_fallback(
    transaction_with_leaked_openai_key: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that empty patterns list falls back to defaults and still detects keys."""
    # Empty list should fallback to default patterns, so it should still detect the OpenAI key
    policy = LeakedApiKeyDetectionPolicy(patterns=[])

    # Should still raise because empty patterns fallback to defaults
    with pytest.raises(LeakedApiKeyError, match="Potential API key detected in message content"):
        await policy.apply(transaction_with_leaked_openai_key, mock_container, mock_db_session)


def test_leaked_api_key_detection_policy_check_text_method():
    """Test the internal _check_text method."""
    policy = LeakedApiKeyDetectionPolicy()

    # Test clean text
    assert not policy._check_text("This is a clean message with no secrets.")

    # Test text with OpenAI key
    assert policy._check_text("My key is sk-abcdefghijklmnopqrstuvwxyz1234567890abcdefghijklmn.")

    # Test text with Slack token
    assert policy._check_text("Use token: xoxb-1234567890123-1234567890123-AbCdEfGhIjKlMnOpQrStUvWx")

    # Test text with GitHub PAT
    github_pat = "github_pat_1234567890123456789012_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567"
    assert policy._check_text(f"My GitHub token is {github_pat}")


def test_leaked_api_key_detection_policy_check_text_with_custom_patterns():
    """Test the _check_text method with custom patterns."""
    policy = LeakedApiKeyDetectionPolicy(patterns=["custom-[0-9]+", "secret-[a-zA-Z]{5}"])

    # Test text that matches first pattern
    assert policy._check_text("My key is custom-12345")

    # Test text that matches second pattern
    assert policy._check_text("The secret is secret-abcde")

    # Test text that doesn't match any pattern
    assert not policy._check_text("This is a clean message")

    # Test text that doesn't match the specific pattern format
    assert not policy._check_text("My key is custom-abc")  # letters instead of numbers


def test_leaked_api_key_detection_policy_serialize_default():
    """Test serialization with default values."""
    policy = LeakedApiKeyDetectionPolicy()

    serialized = policy.serialize()

    expected = {
        "name": "LeakedApiKeyDetectionPolicy",
        "patterns": LeakedApiKeyDetectionPolicy.DEFAULT_PATTERNS,
        "type": "LeakedApiKeyDetection",
    }
    assert serialized == expected


def test_leaked_api_key_detection_policy_serialize_custom():
    """Test serialization with custom values."""
    custom_patterns = ["pattern1", "pattern2"]
    custom_name = "CustomDetector"

    policy = LeakedApiKeyDetectionPolicy(patterns=custom_patterns, name=custom_name)

    serialized = policy.serialize()

    expected = {
        "name": custom_name,
        "patterns": custom_patterns,
        "type": "LeakedApiKeyDetection",
    }
    assert serialized == expected


def test_leaked_api_key_detection_policy_from_serialized_full_config():
    """Test deserialization with full configuration."""
    config = {
        "name": "DeserializedPolicy",
        "patterns": ["custom-[0-9]+", "secret-[a-zA-Z]{5}"],
    }

    policy = LeakedApiKeyDetectionPolicy.from_serialized(config)

    assert policy.name == "DeserializedPolicy"
    assert policy.patterns == ["custom-[0-9]+", "secret-[a-zA-Z]{5}"]


def test_leaked_api_key_detection_policy_from_serialized_with_defaults():
    """Test deserialization with minimal config uses defaults."""
    config = cast(
        SerializableDict,
        {
            "name": "MinimalConfig",
        },
    )

    policy = LeakedApiKeyDetectionPolicy.from_serialized(config)

    assert policy.name == "MinimalConfig"
    assert policy.patterns == LeakedApiKeyDetectionPolicy.DEFAULT_PATTERNS


def test_leaked_api_key_detection_policy_from_serialized_empty_config():
    """Test deserialization with empty config uses all defaults."""
    config = {}

    policy = LeakedApiKeyDetectionPolicy.from_serialized(config)

    assert policy.name == "LeakedApiKeyDetectionPolicy"
    assert policy.patterns == LeakedApiKeyDetectionPolicy.DEFAULT_PATTERNS


def test_leaked_api_key_detection_policy_from_serialized_invalid_patterns_type():
    """Test that ValueError is raised for invalid patterns type."""
    config = cast(
        SerializableDict,
        {
            "name": "TestPolicy",
            "patterns": "not_a_list",  # Should be a list
        },
    )

    with pytest.raises(ValueError, match="'patterns' must be a list of strings"):
        LeakedApiKeyDetectionPolicy.from_serialized(config)


def test_leaked_api_key_detection_policy_from_serialized_invalid_patterns_content():
    """Test that ValueError is raised for invalid patterns content."""
    config = {
        "name": "TestPolicy",
        "patterns": ["valid_pattern", 123, "another_valid_pattern"],  # Contains non-string
    }

    with pytest.raises(ValueError, match="'patterns' must be a list of strings"):
        LeakedApiKeyDetectionPolicy.from_serialized(config)


def test_leaked_api_key_detection_policy_round_trip_serialization():
    """Test serialization and deserialization round trip."""
    custom_patterns = ["custom-[0-9]+", "secret-[a-zA-Z]{5}"]
    original_name = "RoundTripTest"

    original_policy = LeakedApiKeyDetectionPolicy(patterns=custom_patterns, name=original_name)

    # Serialize
    serialized = original_policy.serialize()

    # Deserialize
    restored_policy = LeakedApiKeyDetectionPolicy.from_serialized(serialized)

    # Verify
    assert restored_policy.name == original_policy.name
    assert restored_policy.patterns == original_policy.patterns
    assert restored_policy.serialize() == original_policy.serialize()


@pytest.mark.parametrize(
    "patterns,name",
    [
        (None, None),  # All defaults
        (["custom-[0-9]+"], "CustomPolicy"),  # Custom values
        (LeakedApiKeyDetectionPolicy.DEFAULT_PATTERNS, "DefaultPatterns"),  # Explicit defaults
    ],
)
def test_leaked_api_key_detection_policy_parametrized_initialization(
    patterns: List[str],
    name: str,
):
    """Test initialization with various parameter combinations."""
    if patterns is None and name is None:
        policy = LeakedApiKeyDetectionPolicy()
        expected_name = "LeakedApiKeyDetectionPolicy"
        expected_patterns = LeakedApiKeyDetectionPolicy.DEFAULT_PATTERNS
    elif patterns is None:
        policy = LeakedApiKeyDetectionPolicy(name=name)
        expected_name = name
        expected_patterns = LeakedApiKeyDetectionPolicy.DEFAULT_PATTERNS
    elif name is None:
        policy = LeakedApiKeyDetectionPolicy(patterns=patterns)
        expected_name = "LeakedApiKeyDetectionPolicy"
        expected_patterns = patterns
    else:
        policy = LeakedApiKeyDetectionPolicy(patterns=patterns, name=name)
        expected_name = name
        expected_patterns = patterns

    assert policy.name == expected_name
    assert policy.patterns == expected_patterns
    assert len(policy.compiled_patterns) == len(expected_patterns)
