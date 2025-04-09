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
    """A sample successful backend response object (content not read yet)."""
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
        # Content is None because aread() hasn't been called on *this* object
        content=None,
        request=httpx.Request("GET", "http://backend.test"),
    )


@pytest.fixture
def context_with_raw_body(backend_response: httpx.Response) -> TransactionContext:
    """Context where response object exists and raw body is in data."""
    ctx = TransactionContext(transaction_id="tx-build-test-raw")
    ctx.response = backend_response
    # Simulate raw body read by SendBackendRequestPolicy
    ctx.data["raw_backend_response_body"] = b'{"result": "ok raw"}'
    return ctx


@pytest.fixture
def context_without_response() -> TransactionContext:
    """Context where response is None."""
    return TransactionContext(transaction_id="tx-build-no-resp")


@pytest.fixture
def context_with_modified_data(backend_response: httpx.Response) -> TransactionContext:
    """Context where a policy might have modified status, headers, or content in data."""
    ctx = TransactionContext(transaction_id="tx-build-modified")
    ctx.response = backend_response  # Original response still present
    ctx.data["final_status_code"] = 201
    ctx.data["final_headers"] = {"x-policy-header": "policy-value", "content-type": "text/modified"}
    ctx.data["final_content"] = b"Policy modified content"
    # raw_backend_response_body might still exist but should be ignored if final_content is set
    ctx.data["raw_backend_response_body"] = b"Original raw"
    return ctx


def test_build_response_from_raw_body(builder: DefaultResponseBuilder, context_with_raw_body: TransactionContext):
    """Test building response using context.response and context.data[raw_backend_response_body]."""
    # Act
    fastapi_response = builder.build_response(context_with_raw_body)

    # Assert
    assert isinstance(fastapi_response, Response)
    assert fastapi_response.status_code == 200  # From context.response
    assert fastapi_response.body == b'{"result": "ok raw"}'  # From context.data
    # Check headers (case-insensitive access)
    assert fastapi_response.headers.get("content-type") == "application/json"
    assert fastapi_response.headers.get("x-custom-backend") == "value"
    assert fastapi_response.headers.get("date") == "some-date"
    # Check filtered hop-by-hop headers (except Content-Length which FastAPI adds back)
    assert "transfer-encoding" not in fastapi_response.headers
    assert "connection" not in fastapi_response.headers
    # Check FastAPI added the correct Content-Length
    expected_len = len(b'{"result": "ok raw"}')
    assert fastapi_response.headers.get("content-length") == str(expected_len)


def test_build_response_from_modified_data(
    builder: DefaultResponseBuilder, context_with_modified_data: TransactionContext
):
    """Test building response preferring final values set in context.data by policies."""
    # Act
    fastapi_response = builder.build_response(context_with_modified_data)

    # Assert
    assert isinstance(fastapi_response, Response)
    assert fastapi_response.status_code == 201  # From context.data["final_status_code"]
    assert fastapi_response.body == b"Policy modified content"  # From context.data["final_content"]
    # Check headers from context.data["final_headers"]
    assert fastapi_response.headers.get("x-policy-header") == "policy-value"
    assert fastapi_response.headers.get("content-type") == "text/modified"
    # Check that original backend headers are NOT present
    assert "x-custom-backend" not in fastapi_response.headers
    assert "date" not in fastapi_response.headers

    # Check FastAPI added correct Content-Length for modified content
    expected_len_modified = len(b"Policy modified content")
    assert fastapi_response.headers.get("content-length") == str(expected_len_modified)

    # Check hop-by-hop headers are still filtered (even if accidentally added by a policy)
    ctx = context_with_modified_data
    # Ensure original final_headers is used for the next check
    ctx.data["final_headers"] = {
        "x-policy-header": "policy-value",
        "content-type": "text/modified",
        "connection": "keep-alive",
    }
    fastapi_response_filtered = builder.build_response(ctx)
    assert "connection" not in fastapi_response_filtered.headers
    # Content-Length should still be present and correct even if Connection was filtered
    assert fastapi_response_filtered.headers.get("content-length") == str(expected_len_modified)


def test_build_response_no_context_response(
    builder: DefaultResponseBuilder, context_without_response: TransactionContext
):
    """Test building response when context.response is None (error case)."""
    # Act
    fastapi_response = builder.build_response(context_without_response)

    # Assert
    assert isinstance(fastapi_response, Response)
    assert fastapi_response.status_code == 500
    assert b"Internal Server Error: No response generated" in fastapi_response.body
    assert fastapi_response.headers.get("content-type") == "text/plain; charset=utf-8"


# TODO: Add test case where response exists but body is None/missing in data (should probably error or use empty body?)
# TODO: Add test case with different header casing in backend response / final_headers
# TODO: Add test case where final_content is not bytes (should it try to encode? error?)
# TODO: Test media_type determination based on Content-Type header?
