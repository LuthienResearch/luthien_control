import httpx
import pytest
from fastapi.concurrency import run_in_threadpool

# Import the Settings type and the fixture
from luthien_control.config.settings import Settings

# Import the app fixture
from tests.conftest import app

# No longer requires manually running the server
# Requires .env file with BACKEND_URL=https://api.openai.com and valid OPENAI_API_KEY
# Run with: poetry run pytest -m integration

pytestmark = pytest.mark.integration

# Remove BASE_URL constant
# BASE_URL = "http://127.0.0.1:8000"
PROXY_TIMEOUT = 30.0  # Increase timeout for potentially slower live API calls


@pytest.mark.asyncio
# Inject the app fixture along with settings
async def test_proxy_openai_chat_completions(app, integration_settings: Settings):
    """Test basic chat completions call via the proxy to live OpenAI API.
    Runs against the app instance directly using httpx.
    """
    # The fixture already skips if the key is not found
    assert integration_settings.OPENAI_API_KEY is not None

    endpoint = "/v1/chat/completions"
    headers = {
        # Use the key loaded by the fixture
        "Authorization": f"Bearer {integration_settings.OPENAI_API_KEY.get_secret_value()}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "gpt-3.5-turbo",  # Or a model you have access to
        "messages": [{"role": "user", "content": "Say 'test successful'"}],
        "max_tokens": 10,
    }

    # Use httpx with the app instance directly via ASGITransport
    # Manually handle the lifespan context
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver", timeout=PROXY_TIMEOUT
        ) as client:
            try:
                # Use run_in_threadpool if the actual call blocks,
                # but httpx.post is async, so direct await is fine.
                response = await client.post(endpoint, headers=headers, json=data)
                response.raise_for_status()  # Raise exception for 4xx/5xx errors

                assert response.status_code == 200
                response_data = response.json()
                assert "choices" in response_data
                assert len(response_data["choices"]) > 0
                assert "message" in response_data["choices"][0]
                assert "content" in response_data["choices"][0]["message"]
                print(
                    f"\nIntegration Test Response Content: {response_data['choices'][0]['message']['content']}\n"
                )
                # Basic check that the response seems valid
                assert isinstance(
                    response_data["choices"][0]["message"]["content"], str
                )
            except httpx.ConnectError as e:
                # This error shouldn't happen when running directly against the app
                pytest.fail(f"Unexpected connection error: {e}")
            except httpx.HTTPStatusError as e:
                # Provide more context from the response if available
                pytest.fail(
                    f"Proxy returned an error status {e.response.status_code}: {e.response.text}"
                )
            except Exception as e:
                pytest.fail(
                    f"An unexpected error occurred during the integration test: {e}"
                )


@pytest.mark.asyncio
@pytest.mark.integration  # Ensure this test is marked for integration runs
async def test_proxy_openai_bad_api_key(app):  # Inject app fixture
    """Test that using a bad API key results in a 401 Unauthorized error from the backend."""
    endpoint = "/v1/chat/completions"
    headers = {
        "Authorization": "Bearer sk-INVALID_KEY",  # Use a known bad key
        "Content-Type": "application/json",
    }
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "This should fail"}],
        "max_tokens": 5,
    }

    # Expect an HTTPStatusError (specifically 401)
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        # Use httpx with the app instance directly via ASGITransport
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver", timeout=PROXY_TIMEOUT
        ) as client:
            # Manually handle the lifespan context
            async with app.router.lifespan_context(app):
                response = await client.post(endpoint, headers=headers, json=data)
                print(
                    f"\nBad Key Test Response Status: {response.status_code}"
                )  # Debug
                print(f"Bad Key Test Response Text: {response.text}")  # Debug
                response.raise_for_status()  # This should raise the HTTPStatusError

    # Check that the exception indicates a 401 Unauthorized error
    assert exc_info.value.response.status_code == 401
    print(f"\nSuccessfully received expected 401 for bad API key.")
