import httpx
import pytest
from fastapi.concurrency import run_in_threadpool
import os
from fastapi.testclient import TestClient
from luthien_control.config.settings import Settings

# Import the Settings type and the fixture
from luthien_control.config.settings import Settings

# No longer requires manually running the server
# Requires .env file with BACKEND_URL=https://api.openai.com and valid OPENAI_API_KEY
# Run with: poetry run pytest -m integration

pytestmark = pytest.mark.integration

# Remove BASE_URL constant
# BASE_URL = "http://127.0.0.1:8000"
PROXY_TIMEOUT = 30.0  # Increase timeout for potentially slower live API calls


# The 'client' fixture is automatically available from tests/conftest.py
# The 'integration_settings' fixture is also available from tests/conftest.py

# This test uses the TestClient fixture now, remove app injection
# @pytest.mark.asyncio
# async def test_proxy_openai_chat_completions(app, integration_settings: Settings):
# ... (Remove this function or adapt if needed separately)

# This test uses the TestClient fixture now, remove app injection
# @pytest.mark.asyncio
# @pytest.mark.integration
# async def test_proxy_openai_bad_api_key(app):
# ... (Remove this function or adapt if needed separately)

def test_proxy_openai_chat_completion_real(client: TestClient, integration_settings: Settings):
    """
    Test end-to-end chat completion proxying to the real backend API.
    Requires OPENAI_API_KEY environment variable to be set.
    Requires the configured TARGET_BACKEND_URL to be reachable.
    """
    api_key = integration_settings.OPENAI_API_KEY
    target_backend_host = integration_settings.BACKEND_URL.host

    # Debug: Print loaded key prefix/suffix to verify
    if api_key:
        loaded_key_value = api_key.get_secret_value()
        print(f"\n---> [DEBUG] Loaded API Key Prefix/Suffix: {loaded_key_value[:5]}...{loaded_key_value[-4:]} <---")
    else:
        print("\n---> [DEBUG] API Key loaded as None <---")

    # Use os.getenv to check env var directly, as settings might load from .env
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("Skipping real API test: OPENAI_API_KEY environment variable not set.")
    if not api_key:
        pytest.skip("Skipping real API test: OPENAI_API_KEY not found in settings.")
    if not target_backend_host or "mock-backend.test" in target_backend_host:
        pytest.skip("Skipping real API test: BACKEND_URL is not configured for a real endpoint.")

    # Use the TestClient fixture which uses the main app
    headers = {
        # Explicitly get the secret value for the header
        "Authorization": f"Bearer {api_key.get_secret_value()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-3.5-turbo", # Use a common/cheap model
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
    print(f"Real API response content: {response_data['choices'][0]['message']['content']}") # For visibility
