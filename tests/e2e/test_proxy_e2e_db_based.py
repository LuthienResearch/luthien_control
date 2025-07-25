import httpx
import pytest

# Mark all tests in this module as 'e2e'
pytestmark = [pytest.mark.e2e, pytest.mark.asyncio]


# --- Helper Functions ---


def get_test_request_payload() -> dict:
    """Get standard test request payload for chat completions."""
    return {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the square root of 64?"},
        ],
        "max_tokens": 30,
    }


async def make_chat_completion_request(client: httpx.AsyncClient) -> dict:
    """Make a chat completion request and return the response data."""
    request_payload = get_test_request_payload()

    try:
        response = await client.post("/api/v1/chat/completions", json=request_payload)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        pytest.fail(
            f"API E2E test failed with status {e.response.status_code}. "
            f"Request: {e.request.content}. Response: {e.response.text}"
        )
    except httpx.RequestError as e:
        pytest.fail(f"API E2E test failed with connection error: {e}")
    except Exception as e:
        pytest.fail(f"API E2E test failed with unexpected error: {e}")


# --- Test Cases ---


async def test_e2e_api_chat_completion_comprehensive(e2e_client_db_based: httpx.AsyncClient):
    """
    Comprehensive E2E test for the /api/v1/chat/completions endpoint using database-based policy.

    Tests the complete API response structure, types, and values in a single test
    to avoid multiple API calls while maintaining thorough validation.
    """
    print(f"\nTesting API against base URL (db-based): {e2e_client_db_based.base_url}")

    # Make the API request
    request_payload = get_test_request_payload()
    response = await e2e_client_db_based.post("/api/v1/chat/completions", json=request_payload)

    # Test 1: HTTP status code
    assert response.status_code == 200

    response_data = response.json()

    # Test 2: Top-level response structure
    assert "id" in response_data
    assert "object" in response_data
    assert "created" in response_data
    assert "model" in response_data
    assert "choices" in response_data
    assert "usage" in response_data

    # Test 3: Response field types
    assert isinstance(response_data["created"], int)
    assert isinstance(response_data["model"], str)
    assert isinstance(response_data["choices"], list)
    assert isinstance(response_data["usage"], dict)

    # Test 4: Response field values
    assert response_data["id"].startswith("chatcmpl-")
    assert response_data["object"] == "chat.completion"
    assert len(response_data["choices"]) > 0

    # Test 5: Choice structure
    choice = response_data["choices"][0]
    assert "index" in choice
    assert "message" in choice
    assert "finish_reason" in choice
    assert choice["index"] == 0

    # Test 6: Message structure
    message = choice["message"]
    assert isinstance(message, dict)
    assert message.get("role") == "assistant"
    assert "content" in message
    assert isinstance(message["content"], str)

    # Test 7: Usage structure and values
    usage = response_data["usage"]
    assert "prompt_tokens" in usage
    assert "completion_tokens" in usage
    assert "total_tokens" in usage

    # Verify token counts are positive integers
    assert isinstance(usage["prompt_tokens"], int)
    assert isinstance(usage["completion_tokens"], int)
    assert isinstance(usage["total_tokens"], int)
    assert usage["prompt_tokens"] > 0
    assert usage["completion_tokens"] > 0
    assert usage["total_tokens"] > 0

    print(
        f"API Chat completion E2E test PASSED. Response model: "
        f"{response_data.get('model')}, Finish reason: {choice.get('finish_reason')}"
    )
