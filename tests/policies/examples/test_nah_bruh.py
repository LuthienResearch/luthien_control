import json

import pytest
from fastapi import Request
from fastapi.responses import JSONResponse
from httpx import Headers
from httpx import Request as HttpxRequest
from httpx import Response as HttpxResponse
from luthien_control.policies.examples.nah_bruh import NahBruhPolicy

# --- Fixtures needed for NahBruhPolicy tests (copying for now) ---

@pytest.fixture
def mock_request() -> Request:
    # ... (fixture code copied from original test_examples.py) ...
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
def mock_request_other_path() -> Request:
    # ... (fixture code copied from original test_examples.py) ...
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/v1/models",
        "headers": [],
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
    # ... (fixture code copied from original test_examples.py) ...
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
def request_body_bytes() -> bytes:
    # ... (fixture code copied from original test_examples.py) ...
    return b'{"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "Hello!"}]}'

@pytest.fixture
def response_body_bytes(mock_backend_response: HttpxResponse) -> bytes:
    # ... (fixture code copied from original test_examples.py) ...
    return mock_backend_response.content

@pytest.fixture
def request_id_fixture() -> str:
    # ... (fixture code copied from original test_examples.py) ...
    return "test-req-123"

# --- Test NahBruhPolicy ---

@pytest.mark.asyncio
async def test_nah_bruh_policy_apply_request_intercepts_chat_completion(
    mock_request: Request,  # Use the one with /v1/chat/completions path
    request_body_bytes: bytes,
    request_id_fixture: str,
):
    """Test NahBruhPolicy intercepts chat completion requests."""
    # ... (test code copied from original test_examples.py) ...
    policy = NahBruhPolicy()
    result = await policy.apply_request_policy(
        mock_request, request_body_bytes, request_id_fixture
    )
    assert isinstance(result, JSONResponse)
    assert result.status_code == 200
    response_body = json.loads(result.body.decode())
    assert response_body.get("object") == "chat.completion"
    assert "id" in response_body
    assert "created" in response_body
    assert len(response_body.get("choices", [])) == 1
    choice = response_body["choices"][0]
    assert choice.get("message", {}).get("role") == "assistant"
    assert choice.get("message", {}).get("content") == "nah bruh"
    assert choice.get("finish_reason") == "stop"

@pytest.mark.asyncio
async def test_nah_bruh_policy_apply_request_passes_other_paths(
    mock_request_other_path: Request,  # Use the one with /v1/models path
    request_id_fixture: str,
):
    """Test NahBruhPolicy passes through requests for non-chat-completion paths."""
    # ... (test code copied from original test_examples.py) ...
    policy = NahBruhPolicy()
    empty_body = b""
    result = await policy.apply_request_policy(
        mock_request_other_path, empty_body, request_id_fixture
    )
    expected_result = {
        "url": str(mock_request_other_path.url),
        "headers": dict(mock_request_other_path.headers),
        "content": empty_body,
        "method": mock_request_other_path.method,
    }
    assert isinstance(result, dict)
    assert result == expected_result

@pytest.mark.asyncio
async def test_nah_bruh_policy_apply_response_passes_through(
    mock_backend_response: HttpxResponse,
    response_body_bytes: bytes,
    request_id_fixture: str,
):
    """Test NahBruhPolicy.apply_response_policy passes data through."""
    # ... (test code copied from original test_examples.py) ...
    policy = NahBruhPolicy()
    result = await policy.apply_response_policy(
        mock_backend_response, response_body_bytes, request_id_fixture
    )
    expected_result = {
        "status_code": mock_backend_response.status_code,
        "headers": dict(mock_backend_response.headers),
        "content": response_body_bytes,
    }
    assert isinstance(result, dict)
    assert result == expected_result
