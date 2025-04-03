import pytest
from fastapi import Request
from httpx import Headers
from httpx import Request as HttpxRequest
from httpx import Response as HttpxResponse

# Assuming fixtures might be moved to a conftest.py later, but copying for now
from luthien_control.policies.examples.no_op import NoOpPolicy

# --- Fixtures needed for NoOpPolicy tests ---


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
def mock_backend_response() -> HttpxResponse:
    # ... (fixture code copied from original test_examples.py) ...
    dummy_httpx_request = HttpxRequest(method="POST", url="http://backend/v1/chat/completions")
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


# --- Test NoOpPolicy ---


@pytest.mark.asyncio
async def test_noop_policy_apply_request(
    mock_request: Request,
    request_body_bytes: bytes,
    request_id_fixture: str,
):
    """Test NoOpPolicy.apply_request_policy passes data through."""
    # ... (test code copied from original test_examples.py) ...
    policy = NoOpPolicy()
    result = await policy.apply_request_policy(mock_request, request_body_bytes, request_id_fixture)
    expected_result = {
        "url": str(mock_request.url),
        "headers": dict(mock_request.headers),
        "content": request_body_bytes,
        "method": mock_request.method,
    }
    assert isinstance(result, dict)
    assert result["url"] == expected_result["url"]
    assert result["content"] == expected_result["content"]
    assert result["method"] == expected_result["method"]
    assert len(result["headers"]) == len(expected_result["headers"])


@pytest.mark.asyncio
async def test_noop_policy_apply_response(
    mock_backend_response: HttpxResponse,
    response_body_bytes: bytes,
    request_id_fixture: str,
):
    """Test NoOpPolicy.apply_response_policy passes data through."""
    # ... (test code copied from original test_examples.py) ...
    policy = NoOpPolicy()
    result = await policy.apply_response_policy(mock_backend_response, response_body_bytes, request_id_fixture)
    expected_result = {
        "status_code": mock_backend_response.status_code,
        "headers": dict(mock_backend_response.headers),
        "content": response_body_bytes,
    }
    assert isinstance(result, dict)
    assert result == expected_result
