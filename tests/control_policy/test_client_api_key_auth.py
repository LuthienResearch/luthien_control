"""Tests for ClientApiKeyAuthPolicy."""

import logging
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from luthien_control.api.openai_chat_completions.datatypes import Choice, Message, Usage
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse
from luthien_control.control_policy.client_api_key_auth import ClientApiKeyAuthPolicy
from luthien_control.control_policy.exceptions import (
    ClientAuthenticationError,
    ClientAuthenticationNotFoundError,
)
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.request import Request
from luthien_control.core.request_type import RequestType
from luthien_control.core.response import Response
from luthien_control.core.transaction import Transaction
from luthien_control.db.exceptions import LuthienDBQueryError
from luthien_control.db.sqlmodel_models import ClientApiKey
from psygnal.containers import EventedDict, EventedList
from sqlalchemy.ext.asyncio import AsyncSession

# --- Test Fixtures ---


@pytest.fixture
def sample_transaction() -> Transaction:
    """Provides a Transaction with clean API key for testing."""
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
        api_key="valid-api-key-123",
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

    return Transaction(openai_request=request, openai_response=response, data=transaction_data)


@pytest.fixture
def transaction_with_missing_api_key() -> Transaction:
    """Provides a Transaction with missing API key for testing."""
    request = Request(
        payload=OpenAIChatCompletionsRequest(
            model="gpt-4",
            messages=EventedList([Message(role="user", content="Hello, world!")]),
        ),
        api_endpoint="https://api.openai.com/v1/chat/completions",
        api_key="",  # Empty API key
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

    return Transaction(openai_request=request, openai_response=response, data=EventedDict())


@pytest.fixture
def transaction_with_none_api_key() -> Transaction:
    """Provides a Transaction with None API key for testing."""
    # Create a mock transaction where api_key can be None
    mock_transaction = MagicMock(spec=Transaction)
    mock_request = MagicMock()
    mock_request.api_key = None
    mock_transaction.openai_request = mock_request
    mock_transaction.request_type = RequestType.OPENAI_CHAT
    return mock_transaction


@pytest.fixture
def mock_active_api_key() -> MagicMock:
    """Provides a mock active ClientApiKey."""
    api_key = MagicMock(spec=ClientApiKey)
    api_key.id = 1
    api_key.name = "TestApiKey"
    api_key.value = "valid-api-key-123"
    api_key.is_active = True
    return api_key


@pytest.fixture
def mock_inactive_api_key() -> MagicMock:
    """Provides a mock inactive ClientApiKey."""
    api_key = MagicMock(spec=ClientApiKey)
    api_key.id = 2
    api_key.name = "InactiveApiKey"
    api_key.value = "inactive-api-key-456"
    api_key.is_active = False
    return api_key


@pytest.fixture
def mock_container() -> MagicMock:
    """Provides a mock dependency container."""
    return MagicMock(spec=DependencyContainer)


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Provides a mock database session."""
    return AsyncMock(spec=AsyncSession)


# --- Test Cases ---


def test_client_api_key_auth_policy_initialization_default():
    """Test ClientApiKeyAuthPolicy initialization with default name."""
    _ = ClientApiKeyAuthPolicy()


def test_client_api_key_auth_policy_initialization_custom():
    """Test ClientApiKeyAuthPolicy initialization with custom name."""
    custom_name = "CustomAuthPolicy"
    policy = ClientApiKeyAuthPolicy(name=custom_name)

    assert policy.name == custom_name


@pytest.mark.asyncio
async def test_client_api_key_auth_policy_no_request(
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that policy returns transaction unchanged when there's no request (no-op behavior)."""
    policy = ClientApiKeyAuthPolicy()

    # Create a mock transaction with both request types as None
    mock_transaction = MagicMock(spec=Transaction)
    mock_transaction.openai_request = None
    mock_transaction.raw_request = None

    result = await policy.apply(mock_transaction, mock_container, mock_db_session)

    # Policy should return the transaction unchanged when there's no request (no-op behavior)
    assert result is mock_transaction


@pytest.mark.asyncio
async def test_client_api_key_auth_policy_missing_api_key(
    transaction_with_missing_api_key: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
    caplog,
):
    """Test that ClientAuthenticationNotFoundError is raised when API key is missing."""
    policy = ClientApiKeyAuthPolicy()

    with caplog.at_level(logging.WARNING):
        with pytest.raises(ClientAuthenticationNotFoundError, match="Not authenticated: Missing API key"):
            await policy.apply(transaction_with_missing_api_key, mock_container, mock_db_session)

    assert "Missing API key in transaction request" in caplog.text


@pytest.mark.asyncio
async def test_client_api_key_auth_policy_none_api_key(
    transaction_with_none_api_key: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
    caplog,
):
    """Test that ClientAuthenticationNotFoundError is raised when API key is None."""
    policy = ClientApiKeyAuthPolicy()

    with caplog.at_level(logging.WARNING):
        with pytest.raises(ClientAuthenticationNotFoundError, match="Not authenticated: Missing API key"):
            await policy.apply(transaction_with_none_api_key, mock_container, mock_db_session)

    assert "Missing API key in transaction request" in caplog.text


@pytest.mark.asyncio
async def test_client_api_key_auth_policy_invalid_api_key(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
    caplog,
):
    """Test that ClientAuthenticationError is raised when API key is invalid."""
    from unittest.mock import patch

    policy = ClientApiKeyAuthPolicy()

    # Modify the transaction to use an invalid API key
    assert sample_transaction.openai_request is not None
    sample_transaction.openai_request.api_key = "invalid-api-key"

    with patch("luthien_control.control_policy.client_api_key_auth.get_api_key_by_value") as mock_get_api_key:
        mock_get_api_key.side_effect = LuthienDBQueryError("API key not found")

        with caplog.at_level(logging.WARNING):
            with pytest.raises(ClientAuthenticationError, match="Invalid API Key"):
                await policy.apply(sample_transaction, mock_container, mock_db_session)

        mock_get_api_key.assert_awaited_once_with(mock_db_session, "invalid-api-key")

    assert "Invalid API key provided (key starts with: inva...)" in caplog.text


@pytest.mark.asyncio
async def test_client_api_key_auth_policy_inactive_api_key(
    sample_transaction: Transaction,
    mock_inactive_api_key: MagicMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
    caplog,
):
    """Test that ClientAuthenticationError is raised when API key is inactive."""
    from unittest.mock import patch

    policy = ClientApiKeyAuthPolicy()

    # Modify the transaction to use the inactive API key
    assert sample_transaction.openai_request is not None
    sample_transaction.openai_request.api_key = "inactive-api-key-456"

    with patch("luthien_control.control_policy.client_api_key_auth.get_api_key_by_value") as mock_get_api_key:
        mock_get_api_key.return_value = mock_inactive_api_key

        with caplog.at_level(logging.WARNING):
            with pytest.raises(ClientAuthenticationError, match="Inactive API Key"):
                await policy.apply(sample_transaction, mock_container, mock_db_session)

        mock_get_api_key.assert_awaited_once_with(mock_db_session, "inactive-api-key-456")

    assert "Inactive API key provided (Name: InactiveApiKey, ID: 2)" in caplog.text


@pytest.mark.asyncio
async def test_client_api_key_auth_policy_valid_active_api_key(
    sample_transaction: Transaction,
    mock_active_api_key: MagicMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
    caplog,
):
    """Test successful authentication with a valid, active API key."""
    from unittest.mock import patch

    policy = ClientApiKeyAuthPolicy()

    with patch("luthien_control.control_policy.client_api_key_auth.get_api_key_by_value") as mock_get_api_key:
        mock_get_api_key.return_value = mock_active_api_key

        with caplog.at_level(logging.INFO):
            result = await policy.apply(sample_transaction, mock_container, mock_db_session)

        mock_get_api_key.assert_awaited_once_with(mock_db_session, "valid-api-key-123")

    assert result is sample_transaction
    assert "Client API key authenticated successfully (Name: TestApiKey, ID: 1)" in caplog.text


@pytest.mark.asyncio
async def test_client_api_key_auth_policy_db_query_error(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that LuthienDBQueryError is properly handled."""
    from unittest.mock import patch

    policy = ClientApiKeyAuthPolicy()

    with patch("luthien_control.control_policy.client_api_key_auth.get_api_key_by_value") as mock_get_api_key:
        mock_get_api_key.side_effect = LuthienDBQueryError("Database connection failed")

        with pytest.raises(ClientAuthenticationError, match="Invalid API Key"):
            await policy.apply(sample_transaction, mock_container, mock_db_session)

        mock_get_api_key.assert_awaited_once_with(mock_db_session, "valid-api-key-123")


@pytest.mark.asyncio
async def test_client_api_key_auth_policy_logging_with_custom_name(
    sample_transaction: Transaction,
    mock_active_api_key: MagicMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
    caplog,
):
    """Test that logging includes the custom policy name."""
    from unittest.mock import patch

    policy = ClientApiKeyAuthPolicy(name="CustomAuthPolicy")

    with patch("luthien_control.control_policy.client_api_key_auth.get_api_key_by_value") as mock_get_api_key:
        mock_get_api_key.return_value = mock_active_api_key

        with caplog.at_level(logging.INFO):
            await policy.apply(sample_transaction, mock_container, mock_db_session)

    assert "(ClientApiKeyAuthPolicy)" in caplog.text  # The logger name is still the class name


@pytest.mark.asyncio
async def test_client_api_key_auth_policy_different_api_keys(
    mock_active_api_key: MagicMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test authentication with different API key formats."""
    from unittest.mock import patch

    policy = ClientApiKeyAuthPolicy()

    # Test with various API key formats
    test_api_keys = [
        "sk-1234567890abcdef",
        "api_key_with_underscores",
        "api-key-with-dashes",
        "UPPERCASE_API_KEY",
        "mixed_Case-API_key123",
    ]

    for api_key in test_api_keys:
        # Create a fresh transaction for each test
        request = Request(
            payload=OpenAIChatCompletionsRequest(
                model="gpt-4",
                messages=EventedList([Message(role="user", content="Test")]),
            ),
            api_endpoint="https://api.openai.com/v1/chat/completions",
            api_key=api_key,
        )

        response = Response(
            payload=OpenAIChatCompletionsResponse(
                id="chatcmpl-123",
                object="chat.completion",
                created=1677652288,
                model="gpt-4",
                choices=EventedList(
                    [Choice(index=0, message=Message(role="assistant", content="Response"), finish_reason="stop")]
                ),
                usage=Usage(prompt_tokens=5, completion_tokens=3, total_tokens=8),
            )
        )

        transaction = Transaction(openai_request=request, openai_response=response, data=EventedDict())

        with patch("luthien_control.control_policy.client_api_key_auth.get_api_key_by_value") as mock_get_api_key:
            mock_get_api_key.return_value = mock_active_api_key

            result = await policy.apply(transaction, mock_container, mock_db_session)

            assert result is transaction
            mock_get_api_key.assert_awaited_once_with(mock_db_session, api_key)


def test_client_api_key_auth_policy_serialize_default():
    """Test serialization with default name."""
    policy = ClientApiKeyAuthPolicy()

    serialized = policy.serialize()

    assert serialized["name"] == "ClientApiKeyAuthPolicy"
    assert serialized["type"] == "ClientApiKeyAuth"


def test_client_api_key_auth_policy_serialize_custom():
    """Test serialization with custom name."""
    custom_name = "CustomAuthPolicy"
    policy = ClientApiKeyAuthPolicy(name=custom_name)

    serialized = policy.serialize()

    assert serialized["name"] == custom_name
    assert serialized["type"] == "ClientApiKeyAuth"


def test_client_api_key_auth_policy_from_serialized_with_name():
    """Test deserialization with name in config."""
    config = cast(SerializableDict, {"name": "DeserializedPolicy"})

    policy = ClientApiKeyAuthPolicy.from_serialized(config)

    assert policy.name == "DeserializedPolicy"


def test_client_api_key_auth_policy_from_serialized_without_name():
    """Test deserialization without name in config."""
    config = {}

    policy = ClientApiKeyAuthPolicy.from_serialized(config)

    assert policy.name == "ClientApiKeyAuthPolicy"  # Uses default class name


def test_client_api_key_auth_policy_from_serialized_empty_name():
    """Test deserialization with empty string name."""
    config = cast(SerializableDict, {"name": ""})

    policy = ClientApiKeyAuthPolicy.from_serialized(config)

    assert policy.name == ""


def test_client_api_key_auth_policy_from_serialized_non_string_name():
    """Test deserialization with non-string name raises ValidationError."""
    config = cast(SerializableDict, {"name": 12345})

    with pytest.raises(Exception):  # Pydantic will raise ValidationError for invalid types
        ClientApiKeyAuthPolicy.from_serialized(config)


def test_client_api_key_auth_policy_from_serialized_null_name():
    """Test deserialization with null name is accepted."""
    config = cast(SerializableDict, {"name": None})

    policy = ClientApiKeyAuthPolicy.from_serialized(config)
    assert policy.name is None


def test_client_api_key_auth_policy_round_trip_serialization():
    """Test serialization and deserialization round trip."""
    original_name = "RoundTripTestPolicy"
    original_policy = ClientApiKeyAuthPolicy(name=original_name)

    # Serialize
    serialized = original_policy.serialize()

    # Deserialize
    restored_policy = ClientApiKeyAuthPolicy.from_serialized(serialized)

    # Verify
    assert restored_policy.name == original_policy.name
    assert restored_policy.serialize() == original_policy.serialize()


@pytest.mark.parametrize(
    "name,expected_name",
    [
        (None, "ClientApiKeyAuthPolicy"),  # Default name from class
        ("CustomPolicy", "CustomPolicy"),  # Custom name
        ("Policy123", "Policy123"),  # Alphanumeric name
        ("", ""),  # Empty string
        (
            "Very-Long-Policy-Name-With-Special-Characters!@#$%",
            "Very-Long-Policy-Name-With-Special-Characters!@#$%",
        ),  # Special characters
    ],
)
def test_client_api_key_auth_policy_parametrized_initialization(name: str, expected_name: str):
    """Test initialization with various name parameters."""
    if name is None:
        policy = ClientApiKeyAuthPolicy()
    else:
        policy = ClientApiKeyAuthPolicy(name=name)

    assert policy.name == expected_name


@pytest.mark.asyncio
async def test_client_api_key_auth_policy_preserves_transaction_data(
    sample_transaction: Transaction,
    mock_active_api_key: MagicMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that the policy preserves existing transaction data."""
    from unittest.mock import patch

    policy = ClientApiKeyAuthPolicy()

    # Ensure transaction has some data
    assert sample_transaction.data is not None
    original_data = sample_transaction.data.copy()

    with patch("luthien_control.control_policy.client_api_key_auth.get_api_key_by_value") as mock_get_api_key:
        mock_get_api_key.return_value = mock_active_api_key

        result = await policy.apply(sample_transaction, mock_container, mock_db_session)

    assert result is sample_transaction
    assert result.data == original_data  # Data should be unchanged


@pytest.mark.asyncio
async def test_client_api_key_auth_policy_preserves_request_and_response(
    sample_transaction: Transaction,
    mock_active_api_key: MagicMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that the policy preserves the request and response objects."""
    from unittest.mock import patch

    policy = ClientApiKeyAuthPolicy()

    # Store references to original objects
    original_request = sample_transaction.openai_request
    original_response = sample_transaction.openai_response

    with patch("luthien_control.control_policy.client_api_key_auth.get_api_key_by_value") as mock_get_api_key:
        mock_get_api_key.return_value = mock_active_api_key

        result = await policy.apply(sample_transaction, mock_container, mock_db_session)

    assert result is sample_transaction
    assert result.openai_request is original_request
    assert result.openai_response is original_response


@pytest.mark.asyncio
async def test_client_api_key_auth_policy_api_key_logging_truncation(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
    caplog,
):
    """Test that API key logging is properly truncated for security."""
    from unittest.mock import patch

    policy = ClientApiKeyAuthPolicy()

    # Use a longer API key to test truncation
    long_api_key = "very-long-api-key-that-should-be-truncated-for-security-purposes"
    assert sample_transaction.openai_request is not None
    sample_transaction.openai_request.api_key = long_api_key

    with patch("luthien_control.control_policy.client_api_key_auth.get_api_key_by_value") as mock_get_api_key:
        mock_get_api_key.side_effect = LuthienDBQueryError("API key not found")

        with caplog.at_level(logging.WARNING):
            with pytest.raises(ClientAuthenticationError):
                await policy.apply(sample_transaction, mock_container, mock_db_session)

    # Check that only the first 4 characters are logged
    assert "Invalid API key provided (key starts with: very...)" in caplog.text
    # Ensure the full key is not logged
    assert long_api_key not in caplog.text


@pytest.mark.asyncio
async def test_client_api_key_auth_policy_short_api_key_logging(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
    caplog,
):
    """Test logging behavior with short API keys."""
    from unittest.mock import patch

    policy = ClientApiKeyAuthPolicy()

    # Use a short API key
    short_api_key = "abc"
    assert sample_transaction.openai_request is not None
    sample_transaction.openai_request.api_key = short_api_key

    with patch("luthien_control.control_policy.client_api_key_auth.get_api_key_by_value") as mock_get_api_key:
        mock_get_api_key.side_effect = LuthienDBQueryError("API key not found")

        with caplog.at_level(logging.WARNING):
            with pytest.raises(ClientAuthenticationError):
                await policy.apply(sample_transaction, mock_container, mock_db_session)

    # Check that the truncation works with short keys too
    assert "Invalid API key provided (key starts with: abc...)" in caplog.text


@pytest.mark.asyncio
async def test_client_api_key_auth_policy_raw_request():
    """Test client auth policy with raw request (lines 60-61)."""
    from unittest.mock import patch

    from luthien_control.core.raw_request import RawRequest

    policy = ClientApiKeyAuthPolicy()

    # Create transaction with raw request
    raw_request = RawRequest(
        method="POST",
        path="v1/models",
        headers={"authorization": "Bearer test-raw-api-key"},
        body=b"{}",
        api_key="test-raw-api-key",
    )
    transaction = Transaction(raw_request=raw_request)

    mock_container = MagicMock()
    mock_db_session = AsyncMock()
    mock_active_api_key = MagicMock()
    mock_active_api_key.is_active = True

    with patch("luthien_control.control_policy.client_api_key_auth.get_api_key_by_value") as mock_get_api_key:
        mock_get_api_key.return_value = mock_active_api_key

        result = await policy.apply(transaction, mock_container, mock_db_session)

        # Verify the transaction is returned unchanged and API key was validated
        assert result is transaction
        mock_get_api_key.assert_awaited_once_with(mock_db_session, "test-raw-api-key")
