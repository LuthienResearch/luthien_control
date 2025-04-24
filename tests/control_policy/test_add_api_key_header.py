"""Tests for the AddApiKeyHeaderProcessor."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from luthien_control.control_policy.add_api_key_header import AddApiKeyHeaderPolicy
from luthien_control.control_policy.exceptions import ApiKeyNotFoundError, NoRequestError
from luthien_control.core.transaction_context import TransactionContext


@pytest.fixture
def base_request() -> httpx.Request:
    """Provides a basic httpx request object."""
    # Create a new request for each test to avoid side effects
    return httpx.Request("POST", "http://example.com/api")


@pytest.mark.asyncio
async def test_add_api_key_success(
    base_request: httpx.Request,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test successfully adding the OpenAI API key header."""
    # Instantiate with name (optional)
    policy = AddApiKeyHeaderPolicy(name="TestPolicy")

    context = TransactionContext(transaction_id="test-add-key", request=base_request)

    # Mock the container's settings to return the OpenAI key
    mock_container.settings.get_openai_api_key.return_value = "test-openai-key-123"

    result_context = await policy.apply(context, container=mock_container, session=mock_db_session)
    assert result_context is context
    assert result_context.request is not None
    assert "authorization" in result_context.request.headers
    assert result_context.request.headers["authorization"] == "Bearer test-openai-key-123"
    # Check the correct specific method was called
    mock_container.settings.get_openai_api_key.assert_called_once()


@pytest.mark.asyncio
async def test_add_api_key_missing_key(
    base_request: httpx.Request,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that it raises an error if the OpenAI API key is not configured."""
    policy = AddApiKeyHeaderPolicy()

    context = TransactionContext(transaction_id="test-missing-key", request=base_request)

    # Mock the container's settings to return None for the OpenAI key
    mock_container.settings.get_openai_api_key.return_value = None

    # Update the expected error message to match the implementation
    with pytest.raises(ApiKeyNotFoundError, match="OpenAI API key not configured"):
        await policy.apply(context, container=mock_container, session=mock_db_session)

    # Check the specific method was called
    mock_container.settings.get_openai_api_key.assert_called_once()


@pytest.mark.asyncio
async def test_add_api_key_no_request(
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that it raises an error if the request is not found in the context."""
    policy = AddApiKeyHeaderPolicy()

    context = TransactionContext(transaction_id="test-no-request")
    with pytest.raises(NoRequestError):
        await policy.apply(context, container=mock_container, session=mock_db_session)
    # Ensure get_openai_api_key was NOT called if no request
    mock_container.settings.get_openai_api_key.assert_not_called()


@pytest.mark.asyncio
async def test_add_api_key_overwrites_existing(
    base_request: httpx.Request,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that an existing Authorization header is overwritten."""
    base_request.headers["Authorization"] = "Bearer old-key"
    policy = AddApiKeyHeaderPolicy()

    context = TransactionContext(transaction_id="test-overwrite-key", request=base_request)

    # Mock container's settings for OpenAI key
    mock_container.settings.get_openai_api_key.return_value = "new-openai-key-456"

    result_context = await policy.apply(context, container=mock_container, session=mock_db_session)
    assert result_context is context
    assert result_context.request is not None
    assert "authorization" in result_context.request.headers
    # Verify the new OpenAI key is present
    assert result_context.request.headers["authorization"] == "Bearer new-openai-key-456"
    mock_container.settings.get_openai_api_key.assert_called_once()


@pytest.mark.asyncio
async def test_add_api_key_header_policy_serialization():
    """Test that AddApiKeyHeaderPolicy can be serialized and deserialized correctly."""
    # Arrange - Create instance
    original_policy = AddApiKeyHeaderPolicy(name="CustomPolicyName")

    # Act - Serialize
    serialized_data = original_policy.serialize()

    # Assert Serialization - Only name is expected
    assert isinstance(serialized_data, dict)
    expected_serialized = {
        "name": "CustomPolicyName",
    }
    assert serialized_data == expected_serialized

    # Act - Deserialize
    rehydrated_policy = await AddApiKeyHeaderPolicy.from_serialized(config=serialized_data)

    # Assert Deserialization - Only name is restored
    assert isinstance(rehydrated_policy, AddApiKeyHeaderPolicy)
    assert rehydrated_policy.name == "CustomPolicyName"


@pytest.mark.asyncio
async def test_add_api_key_serialization_defaults():
    """Test serialization when using default name."""
    policy = AddApiKeyHeaderPolicy()

    serialized = policy.serialize()
    # Only default name is expected
    assert serialized == {"name": "AddApiKeyHeaderPolicy"}

    rehydrated = await AddApiKeyHeaderPolicy.from_serialized(serialized)
    assert rehydrated.name == "AddApiKeyHeaderPolicy"
