import json
import pytest
from typing import Any, Dict

from fastapi import Request
from httpx import Headers, Request as HttpxRequest, Response as HttpxResponse

from luthien_control.policies.examples.all_caps import AllCapsPolicy

# --- Fixtures (Copying relevant ones, consider conftest.py later) ---


@pytest.fixture
def mock_request() -> Request:
    # Copied from test_no_op.py
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/v1/chat/completions",
        "headers": [(b"content-type", b"application/json")],
        "client": ("127.0.0.1", 8080),
        "scheme": "http",
        "server": ("localhost", 8000),
        "root_path": "",
        "query_string": b"",
        "http_version": "1.1",
        "asgi": {"version": "3.0"},
        "state": {},
    }
    return Request(scope)


@pytest.fixture
def mock_backend_response() -> HttpxResponse:
    # Copied from test_no_op.py
    dummy_httpx_request = HttpxRequest(
        method="POST", url="http://backend/v1/chat/completions"
    )
    return HttpxResponse(
        status_code=200,
        headers=Headers({"content-type": "application/json"}),
        json={
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1677652288,
            "model": "gpt-3.5-turbo-0125",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Hello there! How may I assist you today?",
                    },
                    "logprobs": None,
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 9, "completion_tokens": 12, "total_tokens": 21},
        },
        request=dummy_httpx_request,
    )

@pytest.fixture
def mock_backend_response_non_json() -> HttpxResponse:
    """Creates a mock httpx Response with non-JSON content."""
    dummy_httpx_request = HttpxRequest(
        method="POST", url="http://backend/v1/chat/completions"
    )
    return HttpxResponse(
        status_code=200,
        headers=Headers({"content-type": "text/plain"}),
        content=b"This is plain text.",
        request=dummy_httpx_request,
    )

@pytest.fixture
def mock_backend_response_not_chat_completion() -> HttpxResponse:
    """Creates a mock httpx Response that is JSON but not chat completion."""
    dummy_httpx_request = HttpxRequest(
        method="GET", url="http://backend/v1/models"
    )
    return HttpxResponse(
        status_code=200,
        headers=Headers({"content-type": "application/json"}),
        json={"object": "list", "data": [{"id": "model-1"}]},
        request=dummy_httpx_request,
    )

@pytest.fixture
def mock_backend_response_error_status() -> HttpxResponse:
    """Creates a mock httpx Response with an error status code."""
    dummy_httpx_request = HttpxRequest(
        method="POST", url="http://backend/v1/chat/completions"
    )
    return HttpxResponse(
        status_code=400,
        headers=Headers({"content-type": "application/json"}),
        json={"error": {"message": "Invalid request"}},
        request=dummy_httpx_request,
    )

@pytest.fixture
def request_body_bytes() -> bytes:
    # Copied from test_no_op.py
    return b'{"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "Hello!"}]}'


@pytest.fixture
def response_body_bytes(mock_backend_response: HttpxResponse) -> bytes:
    # Copied from test_no_op.py
    return mock_backend_response.content


@pytest.fixture
def request_id_fixture() -> str:
    # Copied from test_no_op.py
    return "test-req-123"


# --- Test AllCapsPolicy ---


@pytest.mark.asyncio
async def test_all_caps_policy_apply_request_passes_through(
    mock_request: Request,
    request_body_bytes: bytes,
    request_id_fixture: str,
):
    """Test AllCapsPolicy.apply_request_policy passes data through."""
    policy = AllCapsPolicy()
    result = await policy.apply_request_policy(
        mock_request, request_body_bytes, request_id_fixture
    )
    expected_result = {
        "url": str(mock_request.url),
        "headers": dict(mock_request.headers),
        "content": request_body_bytes,
        "method": mock_request.method,
    }
    assert isinstance(result, dict)
    assert result == expected_result


@pytest.mark.asyncio
async def test_all_caps_policy_apply_response_uppercases_content(
    mock_backend_response: HttpxResponse,
    response_body_bytes: bytes,
    request_id_fixture: str,
):
    """Test AllCapsPolicy correctly uppercases chat completion content."""
    policy = AllCapsPolicy()
    result = await policy.apply_response_policy(
        mock_backend_response, response_body_bytes, request_id_fixture
    )

    assert isinstance(result, dict)
    assert result["status_code"] == mock_backend_response.status_code
    # Headers might change (Content-Length), so check subset or ignore length
    assert "content-type" in result["headers"]

    # Check the content modification
    original_data = json.loads(response_body_bytes.decode())
    result_data = json.loads(result["content"].decode())

    original_content = original_data["choices"][0]["message"]["content"]
    expected_content = original_content.upper()
    actual_content = result_data["choices"][0]["message"]["content"]

    assert actual_content == expected_content

    # Ensure other parts of the JSON are preserved
    assert result_data["id"] == original_data["id"]
    assert result_data["object"] == original_data["object"]
    assert result_data["choices"][0]["message"]["role"] == original_data["choices"][0]["message"]["role"]


@pytest.mark.asyncio
async def test_all_caps_policy_apply_response_passes_through_non_json(
    mock_backend_response_non_json: HttpxResponse,
    request_id_fixture: str,
):
    """Test AllCapsPolicy passes through non-JSON responses unmodified."""
    policy = AllCapsPolicy()
    original_body = mock_backend_response_non_json.content
    result = await policy.apply_response_policy(
        mock_backend_response_non_json, original_body, request_id_fixture
    )

    expected_result = {
        "status_code": mock_backend_response_non_json.status_code,
        "headers": dict(mock_backend_response_non_json.headers),
        "content": original_body,
    }
    assert isinstance(result, dict)
    assert result == expected_result


@pytest.mark.asyncio
async def test_all_caps_policy_apply_response_passes_through_non_chat_completion(
    mock_backend_response_not_chat_completion: HttpxResponse,
    request_id_fixture: str,
):
    """Test AllCapsPolicy passes through non-chat-completion JSON unmodified."""
    policy = AllCapsPolicy()
    original_body = mock_backend_response_not_chat_completion.content
    result = await policy.apply_response_policy(
        mock_backend_response_not_chat_completion, original_body, request_id_fixture
    )

    expected_result = {
        "status_code": mock_backend_response_not_chat_completion.status_code,
        "headers": dict(mock_backend_response_not_chat_completion.headers),
        "content": original_body,
    }
    assert isinstance(result, dict)
    assert result == expected_result

@pytest.mark.asyncio
async def test_all_caps_policy_apply_response_passes_through_error_status(
    mock_backend_response_error_status: HttpxResponse,
    request_id_fixture: str,
):
    """Test AllCapsPolicy passes through responses with error status codes unmodified."""
    policy = AllCapsPolicy()
    original_body = mock_backend_response_error_status.content
    result = await policy.apply_response_policy(
        mock_backend_response_error_status, original_body, request_id_fixture
    )

    expected_result = {
        "status_code": mock_backend_response_error_status.status_code,
        "headers": dict(mock_backend_response_error_status.headers),
        "content": original_body,
    }
    assert isinstance(result, dict)
    assert result == expected_result 