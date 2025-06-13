import httpx
import pytest

# Mark all tests in this module as 'e2e'
pytestmark = [pytest.mark.e2e, pytest.mark.asyncio]


async def test_e2e_api_chat_completion(e2e_client: httpx.AsyncClient):
    """
    Performs an end-to-end test of the /api/chat/completions endpoint.

    Sends a request through the proxy (using the api endpoint) to the actual
    OpenAI backend (or configured backend) and verifies the basic structure
    of the response.
    """
    print(f"\nTesting API against base URL: {e2e_client.base_url}")

    request_payload = {
        "model": "gpt-3.5-turbo",  # Or a model known to be available
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is the square root of 64?"},  # Different prompt
        ],
        "max_tokens": 30,
    }

    try:
        response = await e2e_client.post("/api/chat/completions", json=request_payload)
        response.raise_for_status()  # Raise HTTPStatusError for 4xx/5xx responses

        response_data = response.json()

        # Assertions on the response structure (should match non-beta)
        assert response.status_code == 200
        assert "id" in response_data
        assert response_data["id"].startswith("chatcmpl-")
        assert response_data["object"] == "chat.completion"
        assert "created" in response_data
        assert isinstance(response_data["created"], int)
        assert "model" in response_data
        assert isinstance(response_data["model"], str)
        assert "choices" in response_data
        assert isinstance(response_data["choices"], list)
        assert len(response_data["choices"]) > 0

        choice = response_data["choices"][0]
        assert "index" in choice
        assert choice["index"] == 0
        assert "message" in choice
        assert isinstance(choice["message"], dict)
        assert choice["message"].get("role") == "assistant"
        assert "content" in choice["message"]
        assert isinstance(choice["message"]["content"], str)
        assert "finish_reason" in choice

        assert "usage" in response_data
        assert isinstance(response_data["usage"], dict)
        assert "prompt_tokens" in response_data["usage"]
        assert "completion_tokens" in response_data["usage"]
        assert "total_tokens" in response_data["usage"]

        print(
            f"API Chat completion E2E test PASSED. Response model: "
            f"{response_data.get('model')}, Finish reason: {choice.get('finish_reason')}"
        )

    except httpx.HTTPStatusError as e:
        pytest.fail(
            f"API E2E test failed with status {e.response.status_code}. "
            f"Request: {e.request.content}. Response: {e.response.text}"
        )
    except httpx.RequestError as e:
        pytest.fail(f"API E2E test failed with connection error: {e}")
    except Exception as e:
        pytest.fail(f"API E2E test failed with unexpected error: {e}")
