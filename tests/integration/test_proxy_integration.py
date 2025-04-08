import pytest
from fastapi.testclient import TestClient
from luthien_control.config.settings import Settings
from urllib.parse import urlparse

# Requires .env file with BACKEND_URL=https://api.openai.com and valid OPENAI_API_KEY
# Run with: poetry run pytest -m integration

# Mark all tests in this module as async and integration
pytestmark = [pytest.mark.asyncio, pytest.mark.integration]

# Note: Tests hitting real external APIs (like OpenAI) might be slow
# and require actual credentials in the .env file.

PROXY_TIMEOUT = 30.0  # Increase timeout for potentially slower live API calls


@pytest.mark.asyncio
async def test_proxy_openai_chat_completion_real(client: TestClient):
    """
    Test end-to-end chat completion proxying to the real backend API.
    Requires OPENAI_API_KEY environment variable to be set.
    Requires the configured TARGET_BACKEND_URL to be reachable.
    """
    # Access settings via the attribute set in the conftest fixture
    api_key = client.app.state.test_settings.get_openai_api_key()
    target_backend_url_str = client.app.state.test_settings.get_backend_url()
    target_backend_host = urlparse(target_backend_url_str).netloc

    # Basic check: Ensure API key is loaded
    assert api_key, "BACKEND_API_KEY (or OPENAI_API_KEY) not found in environment/settings"

    # The check below using the loaded settings is correct.
    if not api_key:
        pytest.skip("Skipping real API test: OPENAI_API_KEY not found in settings.")
    if not target_backend_host or "mock-backend.test" in target_backend_host:
        pytest.skip("Skipping real API test: BACKEND_URL is not configured for a real endpoint.")

    # Use the TestClient fixture which uses the main app
    headers = {
        # api_key is now a string, no need for .get_secret_value()
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-3.5-turbo",  # Use a common/cheap model
        "messages": [{"role": "user", "content": "Say this is an integration test!"}],
        "temperature": 0.7,
        "max_tokens": 15,
    }

    # Make the request through the proxy
    # Note: TestClient is synchronous, but it runs the async app correctly
    response = client.post("/v1/chat/completions", headers=headers, json=payload)

    # Basic assertions for a successful response
    assert response.status_code == 200
    response_data = response.json()
    assert "id" in response_data
    assert response_data.get("object") == "chat.completion"
    assert "choices" in response_data
    assert len(response_data["choices"]) > 0
    assert "message" in response_data["choices"][0]
    assert "role" in response_data["choices"][0]["message"]
    assert "content" in response_data["choices"][0]["message"]
    print(f"Real API response content: {response_data['choices'][0]['message']['content']}")  # For visibility
