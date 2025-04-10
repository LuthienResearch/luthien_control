"""Unit tests for InitializeContextPolicy."""

from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import urlparse

import httpx
import pytest
from fastapi import Request as FastAPIRequest  # Use alias to avoid clash
from httpx import Headers, QueryParams
from luthien_control.config.settings import Settings
from luthien_control.control_policy.initialize_context import InitializeContextPolicy
from luthien_control.core.context import TransactionContext
# from luthien_control.core.models import Request as CoreRequest # Removed incorrect import

# Mark all tests in this module as async tests
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_settings() -> MagicMock:
    # Settings are not strictly needed by this policy anymore, but keep for potential future config
    settings = MagicMock(spec=Settings)
    # settings.get_backend_url.return_value = "http://mock-backend.test:8080" # No longer used here
    return settings


@pytest.fixture
def policy(mock_settings: MagicMock) -> InitializeContextPolicy:
    # Pass settings=None if not used, or the mock if potentially used later
    return InitializeContextPolicy(settings=None)


@pytest.fixture
def mock_fastapi_request() -> MagicMock:
    """Provides a mock FastAPI Request object for POST."""
    mock_req = MagicMock(spec=FastAPIRequest)
    # Configure attributes accessed by the policy
    mock_req.method = "POST"
    mock_req.url = httpx.URL("http://proxy.luthien.local:8000/v1/chat/completions?debug=true")
    mock_req.headers = MagicMock()
    mock_req.headers.raw = [  # .raw returns list of (bytes, bytes) tuples
        (b"content-type", b"application/json"),
        (b"accept", b"application/json"),
        (b"authorization", b"Bearer sk-test-key"),
        (b"host", b"proxy.luthien.local:8000"),
    ]
    mock_req.query_params = httpx.QueryParams("debug=true")  # Provide QueryParams object
    mock_req.client = MagicMock()
    mock_req.client.host = "192.168.1.100"
    mock_req.body = AsyncMock(return_value=b'{"model": "gpt-4"}')  # Make body async
    # Add the missing 'scope' attribute
    mock_req.scope = {
        "type": "http",
        "method": "POST",
        "headers": mock_req.headers.raw,  # Use raw headers here too
        "client": (mock_req.client.host, 12345),
        "path_params": {"full_path": "v1/chat/completions"},  # Add path params
        "route": MagicMock(path_format="/api/{full_path:path}"),  # Mock route object
        "path": "/api/v1/chat/completions",
        "query_string": b"debug=true",
        "scheme": "http",
        "server": ("proxy.luthien.local", 8000),
        "root_path": "",
    }
    return mock_req


@pytest.fixture
def mock_fastapi_get_request() -> MagicMock:
    """Provides a mock FastAPI Request object for GET."""
    mock_req = MagicMock(spec=FastAPIRequest)
    mock_req.method = "GET"
    mock_req.url = httpx.URL("http://proxy.luthien.local:8000/v1/models?filter=gpt")
    mock_req.headers = MagicMock()
    mock_req.headers.raw = [
        (b"accept", b"application/json"),
        (b"authorization", b"Bearer sk-test-key"),
        (b"host", b"proxy.luthien.local:8000"),
    ]
    mock_req.query_params = httpx.QueryParams("filter=gpt")
    mock_req.client = MagicMock()
    mock_req.client.host = "10.0.0.1"
    mock_req.body = AsyncMock(return_value=b"")  # Empty body for GET
    # Add the missing 'scope' attribute
    mock_req.scope = {
        "type": "http",
        "method": "GET",
        "headers": mock_req.headers.raw,
        "client": (mock_req.client.host, 54321),
        "path_params": {"full_path": "v1/models"},
        "route": MagicMock(path_format="/api/{full_path:path}"),
        "path": "/api/v1/models",
        "query_string": b"filter=gpt",
        "scheme": "http",
        "server": ("proxy.luthien.local", 8000),
        "root_path": "",
    }
    return mock_req


@pytest.fixture
def base_context() -> TransactionContext:
    """Provides a base TransactionContext for tests."""
    return TransactionContext(transaction_id="tx-init-test")


@pytest.mark.asyncio
async def test_initialize_context_success_post(
    policy: InitializeContextPolicy, mock_fastapi_request: MagicMock, base_context: TransactionContext
):
    """Test successful initialization of context.request for a POST request."""
    # Act
    updated_context = await policy.apply(context=base_context, fastapi_request=mock_fastapi_request)

    # Assert
    assert updated_context is base_context  # Policy should modify in place
    assert updated_context.request is not None
    assert isinstance(updated_context.request, httpx.Request)  # Check for httpx.Request

    core_req = updated_context.request
    assert core_req.method == "POST"
    # URL is placeholder initially, downstream policies set final URL
    # assert core_req.url == mock_fastapi_request.url # Cannot compare directly
    # Headers should be httpx Headers object, check existence via get
    assert core_req.headers.get("content-type") == "application/json"
    assert core_req.headers.get("accept") == "application/json"
    assert core_req.headers.get("authorization") == "Bearer sk-test-key"
    assert core_req.headers.get("host") == "proxy.luthien.local:8000"

    # Client host is not directly stored on httpx.Request
    # The policy extracts it and should store it if needed elsewhere (e.g., context.data)
    # assert core_req.client_host == "192.168.1.100"
    assert core_req.content == b'{"model": "gpt-4"}'
    # Check data stored in context
    assert updated_context.data["raw_request_body"] == b'{"model": "gpt-4"}'
    assert updated_context.data["path_format"] == "/api/{full_path:path}"
    assert updated_context.data["path_params"] == {"full_path": "v1/chat/completions"}
    assert updated_context.data["relative_path"] == "v1/chat/completions"
    mock_fastapi_request.body.assert_awaited_once()


@pytest.mark.asyncio
async def test_initialize_context_success_get(
    policy: InitializeContextPolicy, mock_fastapi_get_request: MagicMock, base_context: TransactionContext
):
    """Test successful initialization of context.request for a GET request."""
    # Act
    updated_context = await policy.apply(context=base_context, fastapi_request=mock_fastapi_get_request)

    # Assert
    assert updated_context is base_context
    assert updated_context.request is not None
    assert isinstance(updated_context.request, httpx.Request)  # Check for httpx.Request

    core_req = updated_context.request
    assert core_req.method == "GET"
    # assert core_req.url == mock_fastapi_get_request.url
    assert core_req.headers.get("accept") == "application/json"
    assert core_req.headers.get("authorization") == "Bearer sk-test-key"
    assert core_req.headers.get("host") == "proxy.luthien.local:8000"

    # assert core_req.client_host == "10.0.0.1"
    assert core_req.content == b""
    assert updated_context.data["raw_request_body"] == b""
    assert updated_context.data["path_format"] == "/api/{full_path:path}"
    assert updated_context.data["path_params"] == {"full_path": "v1/models"}
    assert updated_context.data["relative_path"] == "v1/models"
    mock_fastapi_get_request.body.assert_awaited_once()


@pytest.mark.asyncio
async def test_initialize_context_no_client(
    policy: InitializeContextPolicy, mock_fastapi_request: MagicMock, base_context: TransactionContext
):
    """Test handling when request.client is None."""
    mock_fastapi_request.client = None
    # Update scope accordingly
    mock_fastapi_request.scope["client"] = None

    updated_context = await policy.apply(context=base_context, fastapi_request=mock_fastapi_request)

    # Check that request was still created
    assert updated_context.request is not None
    assert isinstance(updated_context.request, httpx.Request)
    # We don't store client_host on the httpx.Request itself


@pytest.mark.asyncio
async def test_initialize_context_body_read_error(
    policy: InitializeContextPolicy, mock_fastapi_request: MagicMock, base_context: TransactionContext
):
    """Test handling error during request body reading."""
    mock_fastapi_request.body.side_effect = RuntimeError("Stream consumed")

    # The policy now catches this and stores empty bytes, logging an error
    # It should not raise the error itself.
    # with pytest.raises(RuntimeError, match="Stream consumed"):
    updated_context = await policy.apply(context=base_context, fastapi_request=mock_fastapi_request)

    # Context should be populated, but with empty body stored
    assert updated_context.request is not None
    assert isinstance(updated_context.request, httpx.Request)
    assert updated_context.request.content == b""
    assert updated_context.data["raw_request_body"] == b""
    # Path info should still be extracted
    assert updated_context.data["relative_path"] == "v1/chat/completions"
    mock_fastapi_request.body.assert_awaited_once()


@pytest.mark.asyncio
async def test_initialize_context_no_fastapi_request(policy: InitializeContextPolicy, base_context: TransactionContext):
    """Test ValueError if fastapi_request is not provided."""
    with pytest.raises(ValueError, match="fastapi_request must be provided"):
        await policy.apply(context=base_context, fastapi_request=None)


# Remove test related to backend URL error as it's no longer handled here
# async def test_initialize_context_backend_url_error(...):
#     ...

# Existing TODOs are still relevant
# TODO: Add test for requests with different query parameters (multiple, encoding?)
# TODO: Consider edge cases for headers (duplicates, casing - though httpx handles casing)
