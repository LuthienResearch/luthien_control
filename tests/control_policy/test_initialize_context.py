"""Unit tests for InitializeContextPolicy."""

from unittest.mock import AsyncMock, MagicMock

import httpx  # Import httpx for Request object comparison
import pytest
from fastapi import Request
from httpx import Headers, QueryParams
from luthien_control.config.settings import Settings
from luthien_control.control_policy.initialize_context import InitializeContextPolicy
from luthien_control.core.context import TransactionContext

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
    request = MagicMock(spec=Request)
    request.method = "POST"
    # Use a more realistic proxy URL structure
    request.url = "http://proxy.luthien.local:8000/v1/chat/completions?debug=true"

    # Create a separate mock for the headers object
    mock_headers = MagicMock(spec=Headers)
    # Set the .raw attribute on the mock_headers object
    mock_headers.raw = [
        (b"content-type", b"application/json"),
        (b"accept", b"*/*"),
        (b"host", b"proxy.luthien.local:8000"),
        (b"content-length", b"18"),
        (b"x-forwarded-for", b"1.2.3.4"),
    ]
    # Assign the mocked headers object to the request mock
    request.headers = mock_headers

    # FastAPI request.query_params is URL-decoded
    request.query_params = QueryParams({"debug": "true"})
    # Mock the async body() method
    request.body = AsyncMock(return_value=b'{"prompt": "Test"}')
    return request


@pytest.fixture
def mock_fastapi_get_request() -> MagicMock:
    request = MagicMock(spec=Request)
    request.method = "GET"
    request.url = "http://proxy.luthien.local:8000/v1/models?filter=gpt"

    # Create a separate mock for the headers object
    mock_headers = MagicMock(spec=Headers)
    mock_headers.raw = [
        (b"accept", b"application/json"),
        (b"host", b"proxy.luthien.local:8000"),
    ]
    request.headers = mock_headers

    request.query_params = QueryParams({"filter": "gpt"})
    # GET request has no body
    request.body = AsyncMock(return_value=b"")
    return request


@pytest.fixture
def base_context() -> TransactionContext:
    return TransactionContext(transaction_id="tx-init-test")


async def test_initialize_context_success_post(
    policy: InitializeContextPolicy, mock_fastapi_request: MagicMock, base_context: TransactionContext
):
    """Test successful initialization of context.request for a POST request."""
    # Act
    updated_context = await policy.apply(context=base_context, fastapi_request=mock_fastapi_request)

    # Assert
    assert updated_context is base_context  # Should modify in place
    assert updated_context.request is not None
    assert isinstance(updated_context.request, httpx.Request)

    # Check core attributes
    assert updated_context.request.method == "POST"
    # URL should initially match the incoming request URL
    assert str(updated_context.request.url) == "http://proxy.luthien.local:8000/v1/chat/completions?debug=true"

    # Check body was read and stored in request and context.data
    assert updated_context.request.content == b'{"prompt": "Test"}'
    assert updated_context.data.get("raw_request_body") == b'{"prompt": "Test"}'

    # Check headers were copied using raw format
    # httpx.Headers converts keys to lowercase
    assert updated_context.request.headers.get("content-type") == "application/json"
    assert updated_context.request.headers.get("accept") == "*/*"
    assert updated_context.request.headers.get("host") == "proxy.luthien.local:8000"
    assert updated_context.request.headers.get("content-length") == "18"
    assert updated_context.request.headers.get("x-forwarded-for") == "1.2.3.4"


async def test_initialize_context_success_get(
    policy: InitializeContextPolicy, mock_fastapi_get_request: MagicMock, base_context: TransactionContext
):
    """Test successful initialization of context.request for a GET request."""
    # Act
    updated_context = await policy.apply(context=base_context, fastapi_request=mock_fastapi_get_request)

    # Assert
    assert updated_context is base_context
    assert updated_context.request is not None
    assert isinstance(updated_context.request, httpx.Request)
    assert updated_context.request.method == "GET"
    assert str(updated_context.request.url) == "http://proxy.luthien.local:8000/v1/models?filter=gpt"
    assert updated_context.request.content == b""  # GET has no body
    assert updated_context.data.get("raw_request_body") == b""
    assert updated_context.request.headers.get("accept") == "application/json"
    assert updated_context.request.headers.get("host") == "proxy.luthien.local:8000"
    assert "content-length" not in updated_context.request.headers


async def test_initialize_context_missing_request(policy: InitializeContextPolicy, base_context: TransactionContext):
    """Test that passing None for fastapi_request raises a ValueError."""
    # Act & Assert
    with pytest.raises(ValueError, match="fastapi_request must be provided"):
        await policy.apply(context=base_context, fastapi_request=None)

    assert base_context.request is None
    assert "raw_request_body" not in base_context.data


# Remove test related to backend URL error as it's no longer handled here
# async def test_initialize_context_backend_url_error(...):
#     ...

# Existing TODOs are still relevant
# TODO: Add test for requests with different query parameters (multiple, encoding?)
# TODO: Consider edge cases for headers (duplicates, casing - though httpx handles casing)
