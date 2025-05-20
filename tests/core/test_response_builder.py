"""Unit tests for ResponseBuilder."""

import json
import uuid
from typing import AsyncContextManager, cast
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import Response
from fastapi.responses import JSONResponse
from httpx import Headers
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.response_builder import ResponseBuilder
from luthien_control.core.transaction_context import TransactionContext
from luthien_control.settings import Settings
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def builder() -> ResponseBuilder:
    return ResponseBuilder()


@pytest.fixture
def mock_settings_dev_true() -> Settings:
    settings = Settings()
    settings.dev_mode = lambda: True
    return settings


@pytest.fixture
def mock_settings_dev_false() -> Settings:
    settings = Settings()
    settings.dev_mode = lambda: False
    return settings


@pytest.fixture
def mock_dependencies_dev_true(mock_settings_dev_true: Settings) -> DependencyContainer:
    container = DependencyContainer(
        settings=mock_settings_dev_true,
        http_client=AsyncMock(httpx.AsyncClient),
        db_session_factory=AsyncMock(AsyncContextManager[AsyncSession]),
    )
    container.settings = mock_settings_dev_true
    return container


@pytest.fixture
def mock_dependencies_dev_false(mock_settings_dev_false: Settings) -> DependencyContainer:
    container = DependencyContainer(
        settings=mock_settings_dev_false,
        http_client=AsyncMock(httpx.AsyncClient),
        db_session_factory=AsyncMock(AsyncContextManager[AsyncSession]),
    )
    container.settings = mock_settings_dev_false
    return container


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
        content=b'{"result": "from response content"}',
        request=httpx.Request("GET", "http://backend.test"),
    )


@pytest.fixture
def context_with_response_content(backend_response: httpx.Response) -> TransactionContext:
    """Context where response exists and contains content."""
    ctx = TransactionContext(transaction_id=uuid.uuid4())
    ctx.response = backend_response
    return ctx


@pytest.fixture
def context_with_empty_content(backend_response: httpx.Response) -> TransactionContext:
    """Context where response exists, but content is None (e.g., 204)."""
    ctx = TransactionContext(transaction_id=uuid.uuid4())
    empty_response = httpx.Response(
        status_code=204,
        headers=Headers(
            [
                ("content-type", "application/json"),  # Keep some headers to test filtering
                ("x-custom-backend", "value"),
                ("transfer-encoding", "chunked"),
            ]
        ),
        content=None,  # httpx.Response uses None for empty body
        request=backend_response.request,
    )
    ctx.response = empty_response
    return ctx


@pytest.fixture
def context_without_response() -> TransactionContext:
    """Context where response is None."""
    ctx = TransactionContext(transaction_id=uuid.uuid4())
    ctx.response = None  # Explicitly set to None
    return ctx


@pytest.fixture
def context_with_invalid_response_type() -> TransactionContext:
    """Context where response is not an httpx.Response."""
    ctx = TransactionContext(transaction_id=uuid.uuid4())
    ctx.response = "not an httpx.Response object"  # type: ignore
    return ctx


def test_build_response_from_response_content(
    builder: ResponseBuilder,
    context_with_response_content: TransactionContext,
    mock_dependencies_dev_false: DependencyContainer,
):
    """Test building response using context.response status/headers and response.content for content."""
    # Act
    fastapi_response = builder.build_response(context_with_response_content, mock_dependencies_dev_false)

    # Assert
    assert isinstance(fastapi_response, Response)
    assert fastapi_response.status_code == 200  # From context.response
    assert fastapi_response.body == b'{"result": "from response content"}'  # From response.content
    assert fastapi_response.headers.get("content-type") == "application/json"
    assert fastapi_response.headers.get("x-custom-backend") == "value"
    # Check filtered hop-by-hop headers
    assert "transfer-encoding" not in fastapi_response.headers
    assert "connection" not in fastapi_response.headers
    # Content-Length is re-calculated by FastAPI/Starlette
    expected_len = len(b'{"result": "from response content"}')
    assert fastapi_response.headers.get("content-length") == str(expected_len)


def test_build_response_empty_content(
    builder: ResponseBuilder,
    context_with_empty_content: TransactionContext,
    mock_dependencies_dev_false: DependencyContainer,
):
    """Test building response when content is None (e.g., 204 No Content)."""
    # Act
    fastapi_response = builder.build_response(context_with_empty_content, mock_dependencies_dev_false)

    # Assert
    assert isinstance(fastapi_response, Response)
    assert fastapi_response.status_code == 204
    assert fastapi_response.body == b""
    assert fastapi_response.headers.get("content-type") == "application/json"
    assert fastapi_response.headers.get("x-custom-backend") == "value"
    assert "transfer-encoding" not in fastapi_response.headers
    assert fastapi_response.headers.get("content-length") is None


@pytest.mark.parametrize(
    "dev_mode_enabled",
    [
        True,
        False,
    ],
)
def test_build_response_context_response_is_none(
    builder: ResponseBuilder,
    context_without_response: TransactionContext,
    dev_mode_enabled: bool,
    mock_dependencies_dev_true: DependencyContainer,  # Request both
    mock_dependencies_dev_false: DependencyContainer,  # Request both
):
    """Test response when context.response is None"""
    dependencies = mock_dependencies_dev_true if dev_mode_enabled else mock_dependencies_dev_false

    response = builder.build_response(context_without_response, dependencies)
    assert isinstance(response, JSONResponse)
    assert response.status_code == 500


@pytest.mark.parametrize(
    "dev_mode_enabled",
    [
        True,
        False,
    ],
)
def test_build_response_invalid_context_response_type(
    builder: ResponseBuilder,
    context_with_invalid_response_type: TransactionContext,
    dev_mode_enabled: bool,
    mock_dependencies_dev_true: DependencyContainer,  # Request both
    mock_dependencies_dev_false: DependencyContainer,  # Request both
):
    """Test response when context.response is not an httpx.Response instance."""
    dependencies = mock_dependencies_dev_true if dev_mode_enabled else mock_dependencies_dev_false

    # Act
    fastapi_response = builder.build_response(context_with_invalid_response_type, dependencies)

    # Assert
    assert isinstance(fastapi_response, JSONResponse)
    assert fastapi_response.status_code == 500

    response_body = json.loads(cast(bytes, fastapi_response.body).decode("utf-8"))
    assert response_body["transaction_id"] == str(context_with_invalid_response_type.transaction_id)
    if dev_mode_enabled:
        assert "Policy Error:" in response_body["detail"]
        assert "_convert_to_fastapi_response expected httpx.Response, got <class 'str'>" in response_body["detail"]
    else:
        assert response_body["detail"] == "Internal Server Error"
