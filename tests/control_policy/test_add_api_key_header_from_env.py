"""Unit tests for the AddApiKeyHeaderFromEnvPolicy."""

from typing import cast
from unittest.mock import MagicMock

import pytest
from luthien_control.control_policy.add_api_key_header_from_env import AddApiKeyHeaderFromEnvPolicy
from luthien_control.control_policy.exceptions import ApiKeyNotFoundError, NoRequestError
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.transaction_context import TransactionContext


@pytest.fixture
def transaction_context() -> TransactionContext:
    """Provides a real TransactionContext with a mock request object."""
    import uuid

    context = TransactionContext(transaction_id=uuid.UUID("12345678-1234-5678-1234-567812345678"))
    mock_request = MagicMock()
    mock_request.headers = {}
    context.request = mock_request
    context.response = None
    return context


@pytest.fixture
def mock_dependency_container() -> MagicMock:
    """Provides a mock DependencyContainer."""
    return MagicMock()


@pytest.fixture
def mock_async_session() -> MagicMock:
    """Provides a mock AsyncSession."""
    return MagicMock()


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
        assert policy.name == "AddApiKeyHeaderFromEnvPolicy"
        assert policy.api_key_env_var_name == API_KEY_ENV_VAR_NAME

    def test_initialization_empty_env_var_name_raises_value_error(self):
        with pytest.raises(ValueError, match="api_key_env_var_name cannot be empty."):
            AddApiKeyHeaderFromEnvPolicy(api_key_env_var_name="")


class TestAddApiKeyHeaderFromEnvPolicyApply:
    """Tests for the apply method of AddApiKeyHeaderFromEnvPolicy."""

    @pytest.mark.asyncio
    async def test_apply_success(self, transaction_context, mock_dependency_container, mock_async_session, monkeypatch):
        monkeypatch.setenv(API_KEY_ENV_VAR_NAME, API_KEY_VALUE)
        policy = AddApiKeyHeaderFromEnvPolicy(api_key_env_var_name=API_KEY_ENV_VAR_NAME)

        result_context = await policy.apply(transaction_context, mock_dependency_container, mock_async_session)

        assert result_context == transaction_context
        assert "Authorization" in transaction_context.request.headers
        assert transaction_context.request.headers["Authorization"] == f"Bearer {API_KEY_VALUE}"

    @pytest.mark.asyncio
    async def test_apply_no_request_in_context_raises_no_request_error(
        self, transaction_context, mock_dependency_container, mock_async_session
    ):
        transaction_context.request = None
        policy = AddApiKeyHeaderFromEnvPolicy(api_key_env_var_name=API_KEY_ENV_VAR_NAME)

        with pytest.raises(NoRequestError, match=r"\[12345678-1234-5678-1234-567812345678\] No request in context."):
            await policy.apply(transaction_context, mock_dependency_container, mock_async_session)

    @pytest.mark.asyncio
    async def test_apply_env_var_not_set_raises_api_key_not_found_error(
        self, transaction_context, mock_dependency_container, mock_async_session, monkeypatch
    ):
        monkeypatch.delenv(API_KEY_ENV_VAR_NAME, raising=False)
        policy = AddApiKeyHeaderFromEnvPolicy(api_key_env_var_name=API_KEY_ENV_VAR_NAME)

        expected_error_msg_fragment = (
            f"API key not found. Environment variable '{API_KEY_ENV_VAR_NAME}' is not set or is empty."
        )

        with pytest.raises(ApiKeyNotFoundError, match=expected_error_msg_fragment):
            await policy.apply(transaction_context, mock_dependency_container, mock_async_session)

    @pytest.mark.asyncio
    async def test_apply_env_var_set_to_empty_string_raises_api_key_not_found_error(
        self, transaction_context, mock_dependency_container, mock_async_session, monkeypatch
    ):
        monkeypatch.setenv(API_KEY_ENV_VAR_NAME, "")
        policy = AddApiKeyHeaderFromEnvPolicy(api_key_env_var_name=API_KEY_ENV_VAR_NAME)

        expected_error_msg_fragment = (
            f"API key not found. Environment variable '{API_KEY_ENV_VAR_NAME}' is not set or is empty."
        )

        with pytest.raises(ApiKeyNotFoundError, match=expected_error_msg_fragment):
            await policy.apply(transaction_context, mock_dependency_container, mock_async_session)


class TestAddApiKeyHeaderFromEnvPolicySerialization:
    """Tests for serialization and deserialization of AddApiKeyHeaderFromEnvPolicy."""

    def test_serialize(self):
        policy = AddApiKeyHeaderFromEnvPolicy(api_key_env_var_name=API_KEY_ENV_VAR_NAME, name="TestSerialize")
        expected_config = {
            "name": "TestSerialize",
            "api_key_env_var_name": API_KEY_ENV_VAR_NAME,
        }
        assert policy.serialize() == expected_config

    def test_serialize_default_name(self):
        policy = AddApiKeyHeaderFromEnvPolicy(api_key_env_var_name=API_KEY_ENV_VAR_NAME)
        expected_config = {
            "name": "AddApiKeyHeaderFromEnvPolicy",  # Default class name
            "api_key_env_var_name": API_KEY_ENV_VAR_NAME,
        }
        assert policy.serialize() == expected_config

    def test_from_serialized_success(self):
        config = {
            "name": "MyPolicyInstance",
            "api_key_env_var_name": API_KEY_ENV_VAR_NAME,
        }
        policy = AddApiKeyHeaderFromEnvPolicy.from_serialized(cast(SerializableDict, config))
        assert isinstance(policy, AddApiKeyHeaderFromEnvPolicy)
        assert policy.name == "MyPolicyInstance"
        assert policy.api_key_env_var_name == API_KEY_ENV_VAR_NAME

    def test_from_serialized_success_api_key_env_var_name_is_int(self):
        # Test if api_key_env_var_name is converted to string if provided as non-string
        config = {
            "api_key_env_var_name": 12345  # Using an int
        }
        with pytest.raises(TypeError):
            AddApiKeyHeaderFromEnvPolicy.from_serialized(cast(SerializableDict, config))

    def test_from_serialized_missing_api_key_env_var_name_raises_key_error(self):
        config = {"name": "MyPolicyInstance"}  # Missing api_key_env_var_name
        with pytest.raises(
            KeyError, match="Configuration for AddApiKeyHeaderFromEnvPolicy is missing 'api_key_env_var_name'."
        ):
            AddApiKeyHeaderFromEnvPolicy.from_serialized(cast(SerializableDict, config))
