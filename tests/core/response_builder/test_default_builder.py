"""Unit tests for DefaultResponseBuilder."""

import httpx
import pytest
from fastapi import Response
from httpx import Headers
from luthien_control.core.context import TransactionContext
from luthien_control.core.response_builder.default_builder import DefaultResponseBuilder


@pytest.fixture
def builder() -> DefaultResponseBuilder:
    return DefaultResponseBuilder()


@pytest.fixture
def backend_response() -> httpx.Response:
    """A sample successful backend response object with content."""
    return httpx.Response(
        status_code=200,
        headers=Headers(
            [
                ("content-type", "application/json"),
                ("content-length", "123"),  # Should be filtered
                ("transfer-encoding", "chunked"),  # Should be filtered
                ("connection", "close"),  # Should be filtered
                ("x-custom-backend", "value"),
                ("date", "some-date"),  # Example standard header
            ]
        ),
        content=b'{"result": "from response content"}',  # Add actual content here
        request=httpx.Request("GET", "http://backend.test"),
    )


@pytest.fixture
def context_with_raw_body(backend_response: httpx.Response) -> TransactionContext:
    """Context where response exists and raw body is in data (preferred)."""
    ctx = TransactionContext(transaction_id="tx-build-test-raw")
    ctx.response = backend_response
    # Simulate raw body read by SendBackendRequestPolicy
    ctx.data["raw_backend_response_body"] = b'{"result": "ok raw body"}'
    return ctx


@pytest.fixture
def context_with_response_content(backend_response: httpx.Response) -> TransactionContext:
    """Context where response exists, but raw_backend_response_body is not in data."""
    ctx = TransactionContext(transaction_id="tx-build-resp-content")
    ctx.response = backend_response
    # raw_backend_response_body is missing
    return ctx


@pytest.fixture
def context_with_empty_content(backend_response: httpx.Response) -> TransactionContext:
    """Context where response exists, but both raw body and response.content are effectively None/empty."""
    ctx = TransactionContext(transaction_id="tx-build-empty")
    empty_response = httpx.Response(
        status_code=204, headers=backend_response.headers, content=None, request=backend_response.request
    )
    ctx.response = empty_response
    # raw_backend_response_body is missing
    return ctx


@pytest.fixture
def context_without_response() -> TransactionContext:
    """Context where response is None."""
    return TransactionContext(transaction_id="tx-build-no-resp")


def test_build_response_from_raw_body(builder: DefaultResponseBuilder, context_with_raw_body: TransactionContext):
    """Test building response using context.response status/headers and context.data[raw_backend_response_body] for content."""
    # Act
    fastapi_response = builder.build_response(context_with_raw_body)

    # Assert
    assert isinstance(fastapi_response, Response)
    assert fastapi_response.status_code == 200  # From context.response
    assert fastapi_response.body == b'{"result": "ok raw body"}'  # From context.data (preferred)
    # Check headers (case-insensitive access)
    assert fastapi_response.headers.get("content-type") == "application/json"
    assert fastapi_response.headers.get("x-custom-backend") == "value"
    assert fastapi_response.headers.get("date") == "some-date"
    # Check filtered hop-by-hop headers
    assert "transfer-encoding" not in fastapi_response.headers
    assert "connection" not in fastapi_response.headers
    # Check FastAPI added the correct Content-Length
    expected_len = len(b'{"result": "ok raw body"}')
    assert fastapi_response.headers.get("content-length") == str(expected_len)


def test_build_response_from_response_content(
    builder: DefaultResponseBuilder, context_with_response_content: TransactionContext
):
    """Test building response using context.response status/headers and response.content for content."""
    # Act
    fastapi_response = builder.build_response(context_with_response_content)

    # Assert
    assert isinstance(fastapi_response, Response)
    assert fastapi_response.status_code == 200  # From context.response
    assert fastapi_response.body == b'{"result": "from response content"}'  # From response.content
    assert fastapi_response.headers.get("content-type") == "application/json"
    assert fastapi_response.headers.get("x-custom-backend") == "value"
    # Check filtered hop-by-hop headers
    assert "transfer-encoding" not in fastapi_response.headers
    # Check FastAPI added the correct Content-Length
    expected_len = len(b'{"result": "from response content"}')
    assert fastapi_response.headers.get("content-length") == str(expected_len)


def test_build_response_empty_content(builder: DefaultResponseBuilder, context_with_empty_content: TransactionContext):
    """Test building response when content sources are empty (e.g., 204 No Content)."""
    # Act
    fastapi_response = builder.build_response(context_with_empty_content)

    # Assert
    assert isinstance(fastapi_response, Response)
    assert fastapi_response.status_code == 204  # From context.response
    assert fastapi_response.body == b""  # Should be empty
    assert fastapi_response.headers.get("content-type") == "application/json"  # Header still present
    assert fastapi_response.headers.get("x-custom-backend") == "value"
    # Check filtered hop-by-hop headers
    assert "transfer-encoding" not in fastapi_response.headers
    # Check FastAPI added the correct Content-Length
    assert "content-length" not in fastapi_response.headers


def test_build_response_no_context_response(
    builder: DefaultResponseBuilder, context_without_response: TransactionContext
):
    """Test building response when context.response is None (error case)."""
    # Act
    fastapi_response = builder.build_response(context_without_response)

    # Assert
    assert isinstance(fastapi_response, Response)
    assert fastapi_response.status_code == 500
    # Check for the specific error message logged and returned
    # Check for a more general part of the message as TXID is included now
    assert b"Failed to construct final response" in fastapi_response.body
    assert f"TXID: {context_without_response.transaction_id}".encode() in fastapi_response.body
    assert fastapi_response.headers.get("content-type") == "text/plain; charset=utf-8"


# TODO: Add test case where response exists but body is None/missing in data (should probably error or use empty body?)
# TODO: Add test case with different header casing in backend response / final_headers
# TODO: Add test case where final_content is not bytes (should it try to encode? error?)
# TODO: Test media_type determination based on Content-Type header?
