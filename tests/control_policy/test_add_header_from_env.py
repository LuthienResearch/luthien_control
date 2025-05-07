import os
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi import Request as FastAPIRequest
from starlette.datastructures import MutableHeaders

from luthien_control.control_policy.add_header_from_env import AddHeaderFromEnvPolicy
from luthien_control.control_policy.exceptions import NoRequestError
from luthien_control.core.transaction_context import TransactionContext
from luthien_control.core.dependency_container import DependencyContainer


@pytest.fixture
def mock_request_context() -> TransactionContext:
    """Fixture for a basic TransactionContext with a mock request."""
    context = TransactionContext(transaction_id="test-tx-id")
    # Create a mock FastAPIRequest with mutable headers
    mock_fastapi_request = MagicMock(spec=FastAPIRequest)
    mock_fastapi_request.headers = MutableHeaders({})
    context.request = mock_fastapi_request
    return context


@pytest.fixture
def mock_container() -> DependencyContainer:
    """Fixture for a mock DependencyContainer."""
    return AsyncMock(spec=DependencyContainer)


@pytest.fixture
def mock_session() -> AsyncMock:
    """Fixture for a mock AsyncSession."""
    return AsyncMock()


@pytest.mark.asyncio
async def test_add_header_successful(
    mock_request_context: TransactionContext,
    mock_container: DependencyContainer,
    mock_session: AsyncMock,
):
    """Test successful addition of header from an environment variable."""
    header_name = "X-Test-Header"
    env_var_name = "TEST_HEADER_VALUE"
    expected_value = "supersecretvalue"

    policy = AddHeaderFromEnvPolicy(header_name=header_name, env_var_name=env_var_name)

    with patch.dict(os.environ, {env_var_name: expected_value}):
        updated_context = await policy.apply(mock_request_context, mock_container, mock_session)

    assert updated_context.request is not None
    assert updated_context.request.headers[header_name] == expected_value
    assert updated_context.response is None  # No error response should be set


@pytest.mark.asyncio
async def test_add_header_with_custom_name(
    mock_request_context: TransactionContext,
    mock_container: DependencyContainer,
    mock_session: AsyncMock,
):
    """Test successful addition with a custom policy name."""
    header_name = "X-Another-Header"
    env_var_name = "ANOTHER_HEADER_VALUE"
    expected_value = "anothersecret"
    policy_name = "MyCustomHeaderPolicy"

    policy = AddHeaderFromEnvPolicy(header_name=header_name, env_var_name=env_var_name, name=policy_name)
    assert policy.name == policy_name

    with patch.dict(os.environ, {env_var_name: expected_value}):
        updated_context = await policy.apply(mock_request_context, mock_container, mock_session)

    assert updated_context.request is not None
    assert updated_context.request.headers[header_name] == expected_value


@pytest.mark.asyncio
async def test_apply_no_request_in_context(mock_container: DependencyContainer, mock_session: AsyncMock):
    """Test NoRequestError is raised if context.request is None."""
    context = TransactionContext(transaction_id="test-tx-id")  # No request
    policy = AddHeaderFromEnvPolicy(header_name="X-Header", env_var_name="ENV_VAR")

    with pytest.raises(NoRequestError):
        await policy.apply(context, mock_container, mock_session)


@pytest.mark.asyncio
async def test_apply_env_var_not_set(
    mock_request_context: TransactionContext,
    mock_container: DependencyContainer,
    mock_session: AsyncMock,
):
    """Test ConfigurationError and 500 response if env var is not set."""
    header_name = "X-Missing-Header"
    env_var_name = "MISSING_ENV_VAR"

    policy = AddHeaderFromEnvPolicy(header_name=header_name, env_var_name=env_var_name)

    # Ensure the env var is not set
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError) as excinfo:
            await policy.apply(mock_request_context, mock_container, mock_session)

    assert f"Environment variable '{env_var_name}' not set" in str(excinfo.value)
    assert mock_request_context.response is not None
    assert mock_request_context.response.status_code == 500
    response_content = mock_request_context.response.body.decode()
    assert f"Required information not found for header '{header_name}'" in response_content


def test_instantiation_empty_header_name():
    """Test ValueError if header_name is empty."""
    with pytest.raises(ValueError, match="header_name cannot be empty."):
        AddHeaderFromEnvPolicy(header_name="", env_var_name="SOME_ENV_VAR")


def test_instantiation_empty_env_var_name():
    """Test ValueError if env_var_name is empty."""
    with pytest.raises(ValueError, match="env_var_name cannot be empty."):
        AddHeaderFromEnvPolicy(header_name="X-Header", env_var_name="")


@pytest.mark.asyncio
async def test_serialization_deserialization():
    """Test policy serialization and deserialization."""
    original_name = "MyTestPolicy"
    original_header_name = "X-Auth-Token"
    original_env_var_name = "AUTH_TOKEN_ENV"

    policy = AddHeaderFromEnvPolicy(
        name=original_name,
        header_name=original_header_name,
        env_var_name=original_env_var_name,
    )

    serialized_data = policy.serialize()
    assert serialized_data["name"] == original_name
    assert serialized_data["header_name"] == original_header_name
    assert serialized_data["env_var_name"] == original_env_var_name

    rehydrated_policy = await AddHeaderFromEnvPolicy.from_serialized(serialized_data)
    assert rehydrated_policy.name == original_name
    assert rehydrated_policy.header_name == original_header_name
    assert rehydrated_policy.env_var_name == original_env_var_name


@pytest.mark.asyncio
async def test_deserialization_default_name():
    """Test deserialization uses default class name if name is not in config."""
    header_name = "X-Api-Key"
    env_var_name = "API_KEY_VAR"
    config = {"header_name": header_name, "env_var_name": env_var_name}  # No name

    policy = await AddHeaderFromEnvPolicy.from_serialized(config)
    assert policy.name == AddHeaderFromEnvPolicy.__name__
    assert policy.header_name == header_name
    assert policy.env_var_name == env_var_name


@pytest.mark.asyncio
async def test_deserialization_missing_header_name():
    """Test KeyError if header_name is missing during deserialization."""
    config = {"name": "TestPolicy", "env_var_name": "SOME_VAR"}
    with pytest.raises(KeyError):
        await AddHeaderFromEnvPolicy.from_serialized(config)


@pytest.mark.asyncio
async def test_deserialization_missing_env_var_name():
    """Test KeyError if env_var_name is missing during deserialization."""
    config = {"name": "TestPolicy", "header_name": "X-Header"}
    with pytest.raises(KeyError):
        await AddHeaderFromEnvPolicy.from_serialized(config)
