"""Integration tests for the proxy server.

This module contains integration tests for the Luthien Control proxy server.
Tests can be run against either a local server instance or the deployed server.

Usage:
    Run tests against local server (default):
        poetry run pytest -v -m integration

    Run tests against deployed server:
        poetry run pytest -v -m integration --env=deployed

    Run tests against both environments:
        poetry run pytest -v -m integration --env=both

Test Environment Selection:
    --env=local     Run tests against a local server instance (default)
    --env=deployed  Run tests against the deployed server
    --env=both      Run tests against both environments

Notes:
    - The invalid API key test is skipped for deployed instance to avoid security alerts
    - Local server runs on a different port (8765) to avoid conflicts
    - Tests requiring API key will be skipped if OPENAI_API_KEY is not configured
"""

import asyncio
import multiprocessing
import os
import time

import httpx
import pytest
import uvicorn

from luthien_control.proxy.server import app, config

pytestmark = pytest.mark.integration  # Mark all tests in this module as integration tests

# Environment configuration
DEPLOYED_URL = os.getenv("DEPLOYED_URL", "https://luthien-control.fly.dev")
LOCAL_PORT = 8765  # Use a different port than the main server
LOCAL_HOST = "127.0.0.1"


def run_server(host: str, port: int, api_key: str):
    """Run the server in a separate process."""
    config.api_key = api_key  # Set the API key in the server process
    uvicorn.run(app, host=host, port=port, log_level="error")


@pytest.fixture(scope="module")
def local_server():
    """Start a local server in a separate process and clean up after tests."""
    # Store original key to restore later
    original_key = config.api_key

    # Start server process
    process = multiprocessing.Process(target=run_server, args=(LOCAL_HOST, LOCAL_PORT, original_key), daemon=True)
    process.start()

    # Wait for server to start
    time.sleep(1)

    yield f"http://{LOCAL_HOST}:{LOCAL_PORT}"

    # Cleanup
    process.terminate()
    process.join()

    # Restore original key
    config.api_key = original_key


def get_test_environments(request):
    """Get test environments based on command line option."""
    env = request.getoption("--env")
    if env == "both":
        return ["local", "deployed"]
    return [env]


@pytest.fixture
def server_url(request, local_server):
    """Fixture that provides server URL based on selected environment."""
    env = request.config.getoption("--env")

    if env == "local":
        return local_server
    else:  # deployed
        return DEPLOYED_URL


@pytest.fixture
def client(server_url):
    """Create a test client."""
    return httpx.AsyncClient(base_url=server_url)


@pytest.mark.asyncio
async def test_health_check(client):
    """Test that the health check endpoint works."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.asyncio
async def test_openai_chat_completion(client):
    """Test that we can make a chat completion request through the proxy."""
    # Skip if no API key
    if not config.api_key:
        pytest.skip("OpenAI API key not configured")

    # Test request
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say 'test successful' if you receive this message."},
        ],
        "temperature": 0,  # Use 0 for deterministic output
        "max_tokens": 10,  # Keep response short
    }

    response = await client.post("/v1/chat/completions", json=payload)

    # Verify response
    assert response.status_code == 200
    data = response.json()
    assert "choices" in data
    assert len(data["choices"]) > 0
    assert "message" in data["choices"][0]
    assert "content" in data["choices"][0]["message"]
    assert "test successful" in data["choices"][0]["message"]["content"].lower()


@pytest.mark.asyncio
async def test_invalid_endpoint(client):
    """Test that requests to invalid endpoints return appropriate error codes."""
    response = await client.get("/v1/invalid/endpoint")
    assert response.status_code in [404, 401, 403, 500]  # OpenAI may return various error codes


@pytest.mark.asyncio
async def test_invalid_api_key(server_url):
    """Test that requests with invalid API key return 401 Unauthorized."""
    if "fly.dev" in server_url:
        pytest.skip("Skipping invalid API key test for deployed instance")

    # For local instance, start a new server with invalid key
    host = LOCAL_HOST
    port = LOCAL_PORT + 1  # Different port for invalid key test

    process = multiprocessing.Process(target=run_server, args=(host, port, "invalid_key"), daemon=True)
    process.start()
    time.sleep(1)  # Wait for server to start

    try:
        async with httpx.AsyncClient(base_url=f"http://{host}:{port}") as test_client:
            response = await test_client.post(
                "/v1/chat/completions",
                json={"model": "gpt-3.5-turbo", "messages": [{"role": "user", "content": "test"}]},
            )
            assert response.status_code == 401
    finally:
        process.terminate()
        process.join()


@pytest.mark.asyncio
async def test_request_with_policies(client):
    """Test that policies are applied to requests and responses."""
    if not config.api_key:
        pytest.skip("OpenAI API key not configured")

    # Make a request that will go through our policy pipeline
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": "Echo the word 'policy_test'"}],
        "temperature": 0,
    }

    response = await client.post("/v1/chat/completions", json=payload)

    # Verify response
    assert response.status_code == 200
    data = response.json()

    # Verify headers (policies might add headers)
    assert "content-type" in {k.lower(): v for k, v in response.headers.items()}

    # Verify response content
    assert "choices" in data
    assert len(data["choices"]) > 0
    assert "message" in data["choices"][0]
    assert "content" in data["choices"][0]["message"]
    assert "policy_test" in data["choices"][0]["message"]["content"].lower()


@pytest.mark.asyncio
async def test_concurrent_requests(client):
    """Test that the server can handle concurrent requests."""
    if not config.api_key:
        pytest.skip("OpenAI API key not configured")

    # Create multiple concurrent requests
    async def make_request():
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "Say 'concurrent'"}],
            "temperature": 0,
            "max_tokens": 10,
        }
        return await client.post("/v1/chat/completions", json=payload)

    # Make 3 concurrent requests
    responses = await asyncio.gather(*[make_request() for _ in range(3)])

    # Verify all responses
    for response in responses:
        assert response.status_code == 200
        data = response.json()
        assert "choices" in data
        assert len(data["choices"]) > 0
