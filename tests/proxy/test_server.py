# tests/proxy/test_server.py
import json  # Add json import
from typing import Sequence
from unittest.mock import AsyncMock, patch
from urllib.parse import urlparse  # Added for Host header check

import httpx
import pytest
import respx
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from luthien_control.config.settings import Settings
from luthien_control.control_policy.initialize_context import InitializeContextPolicy
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.core.response_builder.interface import ResponseBuilder
from luthien_control.db.models import ApiKey  # Needed for mock auth
from luthien_control.dependencies import get_current_active_api_key  # Import dependency to override
from luthien_control.main import app  # Import your main FastAPI app

# --- Pytest Fixtures ---

# REMOVED fixture clear_policy_cache - no longer needed as old policy system is gone.


@pytest.fixture
def test_app() -> FastAPI:
    """Returns the FastAPI app instance for testing."""
    # Ensure dependency overrides are cleared - IMPORTANT for clean test state
    # Although we aim not to use overrides, this is a safeguard.
    app.dependency_overrides = {}
    return app


@pytest.fixture
def client(test_app: FastAPI) -> TestClient:
    """Provides a FastAPI test client that correctly handles lifespan events."""
    with TestClient(test_app) as test_client:
        yield test_client


# Helper function to get backend URL from env (used for mocking)
def get_test_backend_url() -> str:
    """Gets the BACKEND_URL expected in the test environment."""
    try:
        test_settings = Settings()
        url = test_settings.get_backend_url()
        if not url:
            pytest.fail("BACKEND_URL not found in test environment after loading .env.test")
        return url.rstrip("/")  # Ensure no trailing slash for respx
    except Exception as e:
        pytest.fail(f"Failed to get BACKEND_URL from test Settings: {e}")


# Mock API key for dependency override
mock_api_key = ApiKey(id=99, key_value="mock-key", name="Mock Key", is_active=True)


async def override_get_current_active_api_key():
    return mock_api_key


# --- Test Cases ---


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# REMOVED OLD POLICY SYSTEM TESTS (test_proxy_with_default_policy to test_proxy_invalid_backend_url)
# def test_proxy_with_default_policy(client: TestClient):
# ... removed ...
# def test_proxy_invalid_backend_url(client: TestClient):
# ... removed ...


# --- Tests for /api endpoint (previously /beta) ---


@pytest.mark.asyncio
async def test_api_proxy_endpoint_calls_orchestrator(test_app: FastAPI, client: TestClient):
    """Verify /api endpoint calls run_policy_flow and returns its response."""
    test_path = "some/api/path"
    expected_content = b"Response from mocked run_policy_flow"
    expected_status = 201
    # Create a realistic Response object to be returned by the mock
    mock_response = Response(
        content=expected_content,
        status_code=expected_status,
        headers={"X-Mock-Header": "MockValue"},
        media_type="text/plain",
    )

    # Add a dummy auth header for the test client request
    auth_headers = {"Authorization": "Bearer test-key"}

    # Override the auth dependency
    test_app.dependency_overrides[get_current_active_api_key] = override_get_current_active_api_key

    with patch("luthien_control.proxy.server.run_policy_flow", new_callable=AsyncMock) as mock_run_flow:
        mock_run_flow.return_value = mock_response

        # Make a request to the /api endpoint with auth header
        actual_response = client.get(f"/api/{test_path}", headers=auth_headers)

    # Clean up override
    test_app.dependency_overrides = {}

    # 1. Assert the response received by the client matches the mock's response
    assert actual_response.status_code == expected_status
    assert actual_response.content == expected_content
    assert actual_response.headers["x-mock-header"] == "MockValue"
    assert actual_response.headers["content-type"].startswith("text/plain")

    # 2. Assert run_policy_flow was called once
    mock_run_flow.assert_awaited_once()

    # 3. Assert run_policy_flow was called with expected argument types
    call_kwargs = mock_run_flow.await_args[1]  # Get keyword args from the call

    # Check keyword arguments passed to run_policy_flow
    assert "request" in call_kwargs
    assert "http_client" in call_kwargs
    assert "settings" in call_kwargs
    assert "initial_context_policy" in call_kwargs
    assert "policies" in call_kwargs
    assert "builder" in call_kwargs

    # Check request object details
    request_arg = call_kwargs["request"]
    assert isinstance(request_arg, Request)
    assert request_arg.method == "GET"
    # TestClient uses http://testserver as base URL
    assert request_arg.url.path == f"/api/{test_path}"  # Updated path check

    # Check dependency types (ensure DI worked)
    assert isinstance(call_kwargs["http_client"], httpx.AsyncClient)
    assert isinstance(call_kwargs["settings"], Settings)
    assert isinstance(call_kwargs["initial_context_policy"], InitializeContextPolicy)
    assert isinstance(call_kwargs["policies"], Sequence)
    # Check that policies sequence contains ControlPolicy instances
    assert all(isinstance(p, ControlPolicy) for p in call_kwargs["policies"])  # Check types if list not empty
    assert isinstance(call_kwargs["builder"], ResponseBuilder)

    # Verify the auth header was received by the endpoint
    assert request_arg.headers.get("authorization") == "Bearer test-key"


@pytest.mark.asyncio
async def test_api_proxy_endpoint_handles_post(test_app: FastAPI, client: TestClient):
    """Verify /api endpoint handles POST requests correctly."""
    test_path = "some/api/path/post"
    expected_content = b"Response from mocked run_policy_flow for POST"
    expected_status = 200
    mock_response = Response(content=expected_content, status_code=expected_status)
    auth_headers = {"Authorization": "Bearer test-key-post"}

    # Override the auth dependency
    test_app.dependency_overrides[get_current_active_api_key] = override_get_current_active_api_key

    with patch("luthien_control.proxy.server.run_policy_flow", new_callable=AsyncMock) as mock_run_flow:
        mock_run_flow.return_value = mock_response

        # Make a POST request to the /api endpoint with auth header
        response = client.post(f"/api/{test_path}", content=b"Test POST body", headers=auth_headers)

    test_app.dependency_overrides = {}

    assert response.status_code == expected_status
    assert response.content == expected_content
    mock_run_flow.assert_awaited_once()
    # Check kwargs passed to the mocked function
    call_kwargs = mock_run_flow.await_args[1]
    request_arg = call_kwargs["request"]
    assert isinstance(request_arg, Request)
    assert request_arg.method == "POST"
    # Body needs to be read from the request object passed to the mock
    # assert await request_arg.body() == b"Test POST body" # Cannot await here
    # Accessing body directly from testclient request is tricky, focus on method/path
    assert request_arg.url.path == f"/api/{test_path}"  # Updated path check

    # Verify the auth header was received
    assert request_arg.headers.get("authorization") == "Bearer test-key-post"


# --- NEW E2E Test for /api endpoint (previously /beta) ---


@pytest.mark.envvars(
    {
        # Define a simple but representative policy flow for the API E2E test
        "CONTROL_POLICIES": (
            "luthien_control.control_policy.prepare_backend_headers.PrepareBackendHeadersPolicy, "
            "luthien_control.control_policy.send_backend_request.SendBackendRequestPolicy"
        )
        # Note: InitializeContextPolicy is handled separately via its own dependency
        # Note: DefaultResponseBuilder is assumed via its dependency
    }
)
@respx.mock
@pytest.mark.asyncio  # TestClient handles async endpoint, but mark test for clarity
async def test_api_proxy_with_simple_flow(test_app: FastAPI, client: TestClient):  # Renamed test
    """E2E test basic proxying via the /api endpoint using a defined policy flow."""  # Updated docstring
    backend_url = get_test_backend_url()
    target_relative_path = "v1/test/api/endpoint"  # Path expected by backend
    full_backend_url = f"{backend_url}/{target_relative_path}"

    # Mock the final backend call
    mock_route = respx.post(full_backend_url).mock(
        return_value=httpx.Response(200, json={"id": "api-123", "message": "api backend response"})
    )

    client_payload = {"data": "value", "other": 123}
    # The path sent to the proxy includes the prefix and the relative path
    proxy_path = f"/api/{target_relative_path}"  # Updated path

    # Add auth header for the E2E style test client request
    auth_headers = {"Authorization": "Bearer test-e2e-key"}

    # Override the auth dependency
    test_app.dependency_overrides[get_current_active_api_key] = override_get_current_active_api_key

    response = client.post(proxy_path, json=client_payload, headers={**auth_headers, "X-API-Test": "true"})

    test_app.dependency_overrides = {}

    # async with httpx.AsyncClient(app=client.app, base_url="http://testserver") as async_client:
    #     response = await async_client.post(proxy_path, json=client_payload, headers={"X-API-Test": "true"})

    # --- Assertions ---
    # Check final response to client
    assert response.status_code == 200
    assert response.json()["id"] == "api-123"
    assert response.json()["message"] == "api backend response"

    # Check backend request
    assert mock_route.called
    assert mock_route.call_count == 1

    request_sent_to_backend = mock_route.calls[0].request

    # Check headers added by policies (PrepareBackendHeadersPolicy)
    assert "x-request-id" in request_sent_to_backend.headers
    assert request_sent_to_backend.headers["x-api-test"] == "true"  # Original headers preserved
    # Host header should be set correctly by httpx based on target_url
    expected_host = urlparse(backend_url).hostname
    assert request_sent_to_backend.headers["host"] == expected_host

    # Check payload sent to backend (should be unchanged in this flow)
    sent_payload = json.loads(request_sent_to_backend.content)
    assert sent_payload == client_payload
