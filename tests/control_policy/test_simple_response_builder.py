"""Unit tests for ResponseBuilder implementations."""

import httpx
import pytest
from fastapi import Response, status
from luthien_control.control_policy.simple_response_builder import SimpleResponseBuilder
from luthien_control.core.context import TransactionContext


@pytest.fixture
def simple_builder() -> SimpleResponseBuilder:
    """Provides an instance of SimpleResponseBuilder."""
    return SimpleResponseBuilder()


@pytest.fixture
def base_context() -> TransactionContext:
    """Provides a base TransactionContext with a transaction ID."""
    return TransactionContext(transaction_id="test-tx-123")


def test_simple_builder_with_response(simple_builder: SimpleResponseBuilder, base_context: TransactionContext):
    """Test SimpleResponseBuilder when context.response exists."""
    # Arrange
    test_content = b'{"message": "success"}'
    test_status = 201
    test_headers = {"X-Test-Header": "TestValue", "Content-Type": "application/json"}
    base_context.response = httpx.Response(status_code=test_status, content=test_content, headers=test_headers)

    # Act
    final_response = simple_builder.build_response(base_context)

    # Assert
    assert isinstance(final_response, Response)
    assert final_response.status_code == test_status
    assert final_response.body == test_content
    assert final_response.headers["x-test-header"] == "TestValue"  # Headers are lowercased by FastAPI/Starlette
    assert final_response.headers["content-type"] == "application/json"


def test_simple_builder_without_response(simple_builder: SimpleResponseBuilder, base_context: TransactionContext):
    """Test SimpleResponseBuilder when context.response is None."""
    # Arrange
    base_context.response = None

    # Act & Assert
    # Expecting an error or a default error response. Let's assume a 500 error for now.

    final_response = simple_builder.build_response(base_context)
    assert isinstance(final_response, Response)
    assert final_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert b"Internal server error: No response generated" in final_response.body
