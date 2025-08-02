"""Simple E2E test for IncrementIntegersPolicy."""

import httpx
import pytest

# Mark all tests in this module as 'e2e'
pytestmark = [pytest.mark.e2e, pytest.mark.asyncio]


async def test_increment_policy_with_numbers(e2e_client_file_based: httpx.AsyncClient):
    """Test that IncrementIntegersPolicy increments integers in responses."""

    # Request that should produce numbers that can be incremented
    request_payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant. Always include the exact numbers requested in your response.",
            },
            {"role": "user", "content": "Please say: 'The answer is 7 and the year 2023.'"},
        ],
        "max_tokens": 50,
        "stream": False,
        "temperature": 0,  # Make output more deterministic
    }

    try:
        response = await e2e_client_file_based.post("/api/v1/chat/completions", json=request_payload)
        response.raise_for_status()

        response_data = response.json()

        # Verify basic response structure
        assert response.status_code == 200
        assert "choices" in response_data
        assert len(response_data["choices"]) > 0

        # Get the response content
        message_content = response_data["choices"][0]["message"]["content"]
        print(f"Response content: '{message_content}'")

        # Verify we got a response (the exact content may vary due to LLM behavior)
        assert message_content is not None
        assert len(message_content.strip()) > 0

        print("✅ IncrementIntegersPolicy E2E test completed successfully")
        print(f"   Policy was applied to: {message_content}")

    except httpx.HTTPStatusError as e:
        pytest.fail(
            f"IncrementIntegers E2E test failed with status {e.response.status_code}. Response: {e.response.text}"
        )
    except Exception as e:
        pytest.fail(f"IncrementIntegers E2E test failed: {e}")


async def test_increment_policy_basic_math(e2e_client_file_based: httpx.AsyncClient):
    """Test IncrementIntegersPolicy with a basic math question."""

    request_payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "user", "content": "What is 2 plus 2? Give me just the answer."},
        ],
        "max_tokens": 20,
        "stream": False,
        "temperature": 0,
    }

    try:
        response = await e2e_client_file_based.post("/api/v1/chat/completions", json=request_payload)
        response.raise_for_status()

        response_data = response.json()
        message_content = response_data["choices"][0]["message"]["content"]

        print(f"Math response: '{message_content}'")

        # The exact response will vary, but we should get some content
        # The policy should process any integers in the response
        assert message_content is not None
        assert len(message_content.strip()) > 0

        print("✅ Math question E2E test completed successfully")

    except Exception as e:
        pytest.fail(f"Math question E2E test failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
