"""Tests for the AddApiKeyHeaderProcessor."""

from unittest.mock import MagicMock

import httpx
import pytest
from luthien_control.control_policy.add_api_key_header import AddApiKeyHeaderPolicy
from luthien_control.control_policy.exceptions import ApiKeyNotFoundError, NoRequestError
from luthien_control.core.transaction_context import TransactionContext


@pytest.fixture
def mock_settings() -> MagicMock:
    """Provides a mock Settings object."""
    settings = MagicMock()
    # Default to having an API key
    settings.get_openai_api_key.return_value = "test-api-key-123"
    return settings


@pytest.fixture
def base_request() -> httpx.Request:
    """Provides a basic httpx request object."""
    # Create a new request for each test to avoid side effects
    return httpx.Request("POST", "http://example.com/api")


@pytest.mark.asyncio
async def test_add_api_key_success(mock_settings: MagicMock, base_request: httpx.Request):
    """Test successfully adding the API key header."""
    policy = AddApiKeyHeaderPolicy(settings=mock_settings)
    context = TransactionContext(transaction_id="test-add-key", request=base_request)

    result_context = await policy.apply(context)
    assert result_context is context
    assert result_context.request is not None
    assert "authorization" in result_context.request.headers
    assert result_context.request.headers["authorization"] == "Bearer test-api-key-123"
    mock_settings.get_openai_api_key.assert_called_once()


@pytest.mark.asyncio
async def test_add_api_key_missing_key(mock_settings: MagicMock, base_request: httpx.Request):
    """Test that it raises an error if the API key is not configured."""
    mock_settings.get_openai_api_key.return_value = None  # Configure mock to return None
    policy = AddApiKeyHeaderPolicy(settings=mock_settings)
    context = TransactionContext(transaction_id="test-missing-key", request=base_request)
    with pytest.raises(ApiKeyNotFoundError):
        await policy.apply(context)


@pytest.mark.asyncio
async def test_add_api_key_no_request(mock_settings: MagicMock):
    """Test that it raises an error if the request is not found in the context."""
    policy = AddApiKeyHeaderPolicy(settings=mock_settings)
    context = TransactionContext(transaction_id="test-no-request")
    with pytest.raises(NoRequestError):
        await policy.apply(context)


@pytest.mark.asyncio
async def test_add_api_key_overwrites_existing(mock_settings: MagicMock, base_request: httpx.Request):
    """Test that an existing Authorization header is overwritten."""
    base_request.headers["Authorization"] = "Bearer old-key"
    processor = AddApiKeyHeaderPolicy(settings=mock_settings)
    context = TransactionContext(transaction_id="test-overwrite-key", request=base_request)

    result_context = await processor.apply(context)
    assert result_context is context
    assert result_context.request is not None
    assert "authorization" in result_context.request.headers
    # Verify the new key is present
    assert result_context.request.headers["authorization"] == "Bearer test-api-key-123"
    mock_settings.get_openai_api_key.assert_called_once()
