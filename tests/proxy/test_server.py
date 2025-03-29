"""Unit tests for the proxy server implementation."""

from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from fastapi import HTTPException, Request
from fastapi.datastructures import Headers
from fastapi.testclient import TestClient

from luthien_control.proxy.server import _prepare_request_headers, app


@pytest.fixture
def test_client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_request():
    """Create a mock request with headers."""
    headers = {
        "host": "test.com",
        "content-length": "100",
        "content-type": "application/json",
        "x-custom-header": "value",
    }
    scope = {"type": "http", "headers": [(k.encode(), v.encode()) for k, v in headers.items()]}
    return Request(scope)


@pytest.fixture
def mock_request_with_auth():
    """Create a mock request with authorization header."""
    headers = {
        "host": "test.com",
        "content-length": "100",
        "authorization": "Bearer custom_token",
        "content-type": "application/json",
    }
    scope = {"type": "http", "headers": [(k.encode(), v.encode()) for k, v in headers.items()]}
    return Request(scope)


def test_get_headers_removes_unwanted():
    """Test that _prepare_request_headers removes unwanted headers and adds auth."""
    # Provide a dummy API key for testing the auth addition logic
    dummy_api_key = "test-api-key"
    # Create Headers object directly from raw data for this test
    raw_headers = [
        (b"host", b"test.com"),
        (b"content-length", b"100"),
        (b"content-type", b"application/json"),
        (b"x-custom-header", b"value"),
    ]
    input_headers = Headers(raw=raw_headers)

    headers = _prepare_request_headers(input_headers, dummy_api_key)

    assert isinstance(headers, dict)  # Ensure it returns a dict
    assert "host" not in headers
    assert "content-length" not in headers
    assert headers["content-type"] == "application/json"
    assert headers["x-custom-header"] == "value"
    # Check that the dummy API key was added (using the capitalized key)
    assert "Authorization" in headers
    assert headers["Authorization"] == f"Bearer {dummy_api_key}"


def test_get_headers_preserves_auth():
    """Test that _prepare_request_headers preserves existing authorization header."""
    # API key should not be used if auth header already exists
    dummy_api_key = "test-api-key"
    # Create Headers object directly from raw data for this test
    raw_headers = [
        (b"host", b"test.com"),
        (b"content-length", b"100"),
        (b"authorization", b"Bearer custom_token"),
        (b"content-type", b"application/json"),
    ]
    input_headers = Headers(raw=raw_headers)

    headers = _prepare_request_headers(input_headers, dummy_api_key)

    assert isinstance(headers, dict)  # Ensure it returns a dict
    assert headers["authorization"] == "Bearer custom_token"
    # Check other headers are still present/absent as expected
    assert "host" not in headers
    assert "content-length" not in headers
    assert headers["content-type"] == "application/json"


def test_health_check(test_client):
    """Test the health check endpoint."""
    response = test_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_proxy_request_success():
    """Test successful proxy request with policy application."""
    # Mock request
    mock_body = b'{"test": "data"}'
    mock_query_params = {"param": "value"}
    mock_request = Mock(
        method="POST",
        headers={"content-type": "application/json"},
        body=AsyncMock(return_value=mock_body),
        query_params=mock_query_params,
    )

    # Mock policy manager responses
    mock_processed_request = {
        "target_url": "https://api.test.com/v1/test",
        "headers": {"content-type": "application/json"},
        "body": mock_body,
    }
    mock_processed_response = {
        "status_code": 200,
        "headers": {"content-type": "application/json"},
        "content": b'{"response": "data"}',
    }

    # Mock httpx response
    mock_response = Mock(
        status_code=200,
        headers={"content-type": "application/json"},
        aread=AsyncMock(return_value=b'{"response": "data"}'),
    )

    # Patch dependencies
    with (
        patch(
            "luthien_control.proxy.server.policy_manager.apply_request_policies",
            AsyncMock(return_value=mock_processed_request),
        ),
        patch(
            "luthien_control.proxy.server.policy_manager.apply_response_policies",
            AsyncMock(return_value=mock_processed_response),
        ),
        patch("httpx.AsyncClient.request", AsyncMock(return_value=mock_response)),
        patch("luthien_control.proxy.server.api_logger") as mock_logger,
    ):
        from luthien_control.proxy.server import proxy_request

        response = await proxy_request(mock_request, "test")

        assert response.status_code == 200
        assert response.body == b'{"response": "data"}'
        mock_logger.log_request.assert_called_once()
        mock_logger.log_response.assert_called_once()


@pytest.mark.asyncio
async def test_proxy_request_with_content_encoding():
    """Test proxy request handling content-encoding header."""
    # Mock request
    mock_request = Mock(method="GET", headers={}, query_params={})

    # Mock processed response with content-encoding
    mock_processed_response = {
        "status_code": 200,
        "headers": {"content-encoding": "br, gzip"},
        "content": b"compressed_data",
    }

    # Patch dependencies
    with (
        patch(
            "luthien_control.proxy.server.policy_manager.apply_request_policies",
            AsyncMock(return_value={"target_url": "test", "headers": {}, "body": None}),
        ),
        patch(
            "luthien_control.proxy.server.policy_manager.apply_response_policies",
            AsyncMock(return_value=mock_processed_response),
        ),
        patch("httpx.AsyncClient.request") as mock_request_fn,
        patch("luthien_control.proxy.server.api_logger"),
    ):
        mock_response = Mock(
            status_code=200, headers={"content-encoding": "br, gzip"}, aread=AsyncMock(return_value=b"compressed_data")
        )
        mock_request_fn.return_value = mock_response

        from luthien_control.proxy.server import proxy_request

        response = await proxy_request(mock_request, "test")

        assert response.status_code == 200
        assert response.headers["content-encoding"] == "gzip"  # br should be removed


@pytest.mark.asyncio
async def test_proxy_request_only_br_content_encoding():
    """Test proxy request removing content-encoding header if only 'br' is present."""
    # Mock request
    mock_request = Mock(method="GET", headers={}, query_params={})

    # Mock processed response with only 'br' content-encoding
    mock_processed_response = {"status_code": 200, "headers": {"content-encoding": "br"}, "content": b"compressed_data"}

    # Patch dependencies
    with (
        patch(
            "luthien_control.proxy.server.policy_manager.apply_request_policies",
            AsyncMock(return_value={"target_url": "test", "headers": {}, "body": None}),
        ),
        patch(
            "luthien_control.proxy.server.policy_manager.apply_response_policies",
            AsyncMock(return_value=mock_processed_response),
        ),
        patch("httpx.AsyncClient.request") as mock_request_fn,
        patch("luthien_control.proxy.server.api_logger"),
    ):
        mock_response = Mock(
            status_code=200, headers={"content-encoding": "br"}, aread=AsyncMock(return_value=b"compressed_data")
        )
        mock_request_fn.return_value = mock_response

        from luthien_control.proxy.server import proxy_request

        response = await proxy_request(mock_request, "test")

        assert response.status_code == 200
        assert "content-encoding" not in response.headers  # Header should be removed


@pytest.mark.asyncio
async def test_proxy_request_request_error():
    """Test proxy request handling of RequestError."""
    mock_request = Mock(method="GET", headers={}, query_params={})

    with (
        patch(
            "luthien_control.proxy.server.policy_manager.apply_request_policies",
            AsyncMock(return_value={"target_url": "test", "headers": {}, "body": None}),
        ),
        patch("httpx.AsyncClient.request", AsyncMock(side_effect=httpx.RequestError("Network error"))),
        patch("luthien_control.proxy.server.api_logger"),
    ):
        from luthien_control.proxy.server import proxy_request

        with pytest.raises(HTTPException) as exc_info:
            await proxy_request(mock_request, "test")

        # Expect 502 (Bad Gateway) for proxy errors
        assert exc_info.value.status_code == 502
        assert "Error forwarding request" in exc_info.value.detail


@pytest.mark.asyncio
async def test_proxy_request_unexpected_error():
    """Test proxy request handling of unexpected errors."""
    mock_request = Mock(method="GET", headers={}, query_params={})

    with (
        patch(
            "luthien_control.proxy.server.policy_manager.apply_request_policies",
            AsyncMock(side_effect=ValueError("Unexpected error")),
        ),
        patch("luthien_control.proxy.server.api_logger"),
    ):
        from luthien_control.proxy.server import proxy_request

        with pytest.raises(HTTPException) as exc_info:
            await proxy_request(mock_request, "test")

        assert exc_info.value.status_code == 500
        assert "Unexpected error" in str(exc_info.value.detail)
