"""Tests for the AddApiKeyHeaderProcessor."""

from unittest.mock import MagicMock

import httpx
import pytest
from luthien_control.control_processors.add_api_key_header import AddApiKeyHeaderProcessor
from luthien_control.core.context import TransactionContext


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
    processor = AddApiKeyHeaderProcessor(settings=mock_settings)
    context = TransactionContext(transaction_id="test-add-key", request=base_request)

    # Expect NotImplementedError initially
    # with pytest.raises(NotImplementedError):
    #     await processor.process(context)

    # --- Assertions for implemented logic ---
    result_context = await processor.process(context)
    assert result_context is context
    assert result_context.request is not None
    assert "authorization" in result_context.request.headers
    assert result_context.request.headers["authorization"] == "Bearer test-api-key-123"
    mock_settings.get_openai_api_key.assert_called_once()


@pytest.mark.asyncio
async def test_add_api_key_no_request(mock_settings: MagicMock):
    """Test that it's a no-op if context.request is None."""
    processor = AddApiKeyHeaderProcessor(settings=mock_settings)
    context = TransactionContext(transaction_id="test-no-request")  # request is None

    # Expect NotImplementedError initially
    # with pytest.raises(NotImplementedError):
    #     await processor.process(context)

    # --- Assertions for implemented logic ---
    result_context = await processor.process(context)
    assert result_context is context
    # Should not attempt to get key if there's no request to modify
    mock_settings.get_openai_api_key.assert_not_called()


@pytest.mark.asyncio
async def test_add_api_key_missing_key(mock_settings: MagicMock, base_request: httpx.Request):
    """Test that it's a no-op if the API key is not configured."""
    mock_settings.get_openai_api_key.return_value = None  # Configure mock to return None
    processor = AddApiKeyHeaderProcessor(settings=mock_settings)
    context = TransactionContext(transaction_id="test-missing-key", request=base_request)
    # Clone headers as httpx.Headers are mutable
    original_headers = httpx.Headers(context.request.headers)

    # Expect NotImplementedError initially
    # with pytest.raises(NotImplementedError):
    #     await processor.process(context)

    # --- Assertions for implemented logic ---
    result_context = await processor.process(context)
    assert result_context is context
    assert result_context.request is not None
    # Headers should be unchanged from the original
    assert result_context.request.headers == original_headers
    assert "authorization" not in result_context.request.headers
    mock_settings.get_openai_api_key.assert_called_once()


@pytest.mark.asyncio
async def test_add_api_key_overwrites_existing(mock_settings: MagicMock, base_request: httpx.Request):
    """Test that an existing Authorization header is overwritten."""
    base_request.headers["Authorization"] = "Bearer old-key"
    processor = AddApiKeyHeaderProcessor(settings=mock_settings)
    context = TransactionContext(transaction_id="test-overwrite-key", request=base_request)

    # Expect NotImplementedError initially
    # with pytest.raises(NotImplementedError):
    #     await processor.process(context)

    # --- Assertions for implemented logic ---
    result_context = await processor.process(context)
    assert result_context is context
    assert result_context.request is not None
    assert "authorization" in result_context.request.headers
    # Verify the new key is present
    assert result_context.request.headers["authorization"] == "Bearer test-api-key-123"
    mock_settings.get_openai_api_key.assert_called_once()
