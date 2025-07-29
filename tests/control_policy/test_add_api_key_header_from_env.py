"""Unit tests for the AddApiKeyHeaderFromEnvPolicy."""

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from luthien_control.api.openai_chat_completions.datatypes import Choice, Message, Usage
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse
from luthien_control.control_policy.add_api_key_header_from_env import AddApiKeyHeaderFromEnvPolicy
from luthien_control.control_policy.exceptions import ApiKeyNotFoundError
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
        api_key="initial_key",
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

    return Transaction(openai_request=request, openai_response=response, data=transaction_data)


@pytest.fixture
def mock_dependency_container() -> MagicMock:
    """Provides a mock DependencyContainer."""
    return MagicMock()


@pytest.fixture
def mock_async_session() -> AsyncMock:
    """Provides a mock AsyncSession."""
    return AsyncMock()


API_KEY_ENV_VAR_NAME = "LUTHIEN_CONTROL_API_KEY_FOR_TESTS"
API_KEY_VALUE = "supersecretkey"


class TestAddApiKeyHeaderFromEnvPolicyInit:
    """Tests for AddApiKeyHeaderFromEnvPolicy initialization."""

    def test_initialization_with_name(self):
        policy = AddApiKeyHeaderFromEnvPolicy(api_key_env_var_name=API_KEY_ENV_VAR_NAME, name="MyCustomPolicy")
        assert policy.name == "MyCustomPolicy"
        assert policy.api_key_env_var_name == API_KEY_ENV_VAR_NAME

    def test_initialization_without_name(self):
        policy = AddApiKeyHeaderFromEnvPolicy(api_key_env_var_name=API_KEY_ENV_VAR_NAME)
        assert policy.api_key_env_var_name == API_KEY_ENV_VAR_NAME

    def test_initialization_empty_env_var_name_allowed(self):
        policy = AddApiKeyHeaderFromEnvPolicy(api_key_env_var_name="")
        assert policy.api_key_env_var_name == ""


class TestAddApiKeyHeaderFromEnvPolicyApply:
    """Tests for the apply method of AddApiKeyHeaderFromEnvPolicy."""

    @pytest.mark.asyncio
    async def test_apply_success(self, sample_transaction, mock_dependency_container, mock_async_session, monkeypatch):
        monkeypatch.setenv(API_KEY_ENV_VAR_NAME, API_KEY_VALUE)
        policy = AddApiKeyHeaderFromEnvPolicy(api_key_env_var_name=API_KEY_ENV_VAR_NAME)

        result_transaction = await policy.apply(sample_transaction, mock_dependency_container, mock_async_session)

        assert result_transaction == sample_transaction
        assert result_transaction.openai_request is not None
        assert result_transaction.openai_request.api_key == API_KEY_VALUE

    @pytest.mark.asyncio
    async def test_apply_no_request_in_transaction_returns_unchanged(
        self, mock_dependency_container, mock_async_session
    ):
        # Create a mock transaction with request property that returns None
        mock_transaction = MagicMock(spec=Transaction)
        mock_transaction.openai_request = None
        policy = AddApiKeyHeaderFromEnvPolicy(api_key_env_var_name=API_KEY_ENV_VAR_NAME)

        result = await policy.apply(mock_transaction, mock_dependency_container, mock_async_session)

        # Policy should return the transaction unchanged when there's no request (no-op behavior)
        assert result is mock_transaction

    @pytest.mark.asyncio
    async def test_apply_env_var_not_set_raises_api_key_not_found_error(
        self, sample_transaction, mock_dependency_container, mock_async_session, monkeypatch
    ):
        monkeypatch.delenv(API_KEY_ENV_VAR_NAME, raising=False)
        policy = AddApiKeyHeaderFromEnvPolicy(api_key_env_var_name=API_KEY_ENV_VAR_NAME)

        expected_error_msg_fragment = (
            f"API key not found. Environment variable '{API_KEY_ENV_VAR_NAME}' is not set or is empty."
        )

        with pytest.raises(ApiKeyNotFoundError, match=expected_error_msg_fragment):
            await policy.apply(sample_transaction, mock_dependency_container, mock_async_session)

    @pytest.mark.asyncio
    async def test_apply_env_var_set_to_empty_string_raises_api_key_not_found_error(
        self, sample_transaction, mock_dependency_container, mock_async_session, monkeypatch
    ):
        monkeypatch.setenv(API_KEY_ENV_VAR_NAME, "")
        policy = AddApiKeyHeaderFromEnvPolicy(api_key_env_var_name=API_KEY_ENV_VAR_NAME)

        expected_error_msg_fragment = (
            f"API key not found. Environment variable '{API_KEY_ENV_VAR_NAME}' is not set or is empty."
        )

        with pytest.raises(ApiKeyNotFoundError, match=expected_error_msg_fragment):
            await policy.apply(sample_transaction, mock_dependency_container, mock_async_session)


class TestAddApiKeyHeaderFromEnvPolicySerialization:
    """Tests for serialization and deserialization of AddApiKeyHeaderFromEnvPolicy."""

    def test_serialize(self):
        policy = AddApiKeyHeaderFromEnvPolicy(api_key_env_var_name=API_KEY_ENV_VAR_NAME, name="TestSerialize")
        expected_config = {
            "name": "TestSerialize",
            "api_key_env_var_name": API_KEY_ENV_VAR_NAME,
            "type": "AddApiKeyHeaderFromEnv",
        }
        assert policy.serialize() == expected_config

    def test_serialize_default_name(self):
        policy = AddApiKeyHeaderFromEnvPolicy(api_key_env_var_name=API_KEY_ENV_VAR_NAME)
        serialized = policy.serialize()
        assert "name" not in serialized or serialized.get("name") is None
        assert serialized["api_key_env_var_name"] == API_KEY_ENV_VAR_NAME
        assert serialized["type"] == "AddApiKeyHeaderFromEnv"

    def test_from_serialized_success(self):
        config = {
            "name": "MyPolicyInstance",
            "api_key_env_var_name": API_KEY_ENV_VAR_NAME,
        }
        policy = AddApiKeyHeaderFromEnvPolicy.from_serialized(cast(SerializableDict, config))
        assert isinstance(policy, AddApiKeyHeaderFromEnvPolicy)
        assert policy.name == "MyPolicyInstance"
        assert policy.api_key_env_var_name == API_KEY_ENV_VAR_NAME

    def test_from_serialized_with_invalid_type_raises_error(self):
        """Test that from_serialized raises ValidationError for wrong type."""
        config = {"api_key_env_var_name": 12345}  # Using an int
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AddApiKeyHeaderFromEnvPolicy.from_serialized(cast(SerializableDict, config))

    def test_from_serialized_missing_api_key_env_var_name_raises_validation_error(self):
        config = {"name": "MyPolicyInstance"}  # Missing api_key_env_var_name
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AddApiKeyHeaderFromEnvPolicy.from_serialized(cast(SerializableDict, config))
