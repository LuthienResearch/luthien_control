# tests/proxy/test_server.py
import json  # Add json import
from typing import Sequence
from unittest.mock import AsyncMock, patch
from urllib.parse import urlparse  # Added for Host header check

import httpx
import pytest
import respx
from fastapi import FastAPI, Request, Response, status
from fastapi.testclient import TestClient
from luthien_control.config.settings import Settings
from luthien_control.control_policy.initialize_context import InitializeContextPolicy
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.core.response_builder.interface import ResponseBuilder
from luthien_control.main import app  # Import your main FastAPI app

# --- Pytest Fixtures ---


# Reinstate fixture to clear policy cache between tests
@pytest.fixture(autouse=True)
def clear_policy_cache():
    """Ensure the policy cache in dependencies is cleared before each test."""
    from luthien_control import dependencies

    print("\n[clear_policy_cache] Clearing policy cache.")
    original_cache = dependencies._cached_policy
    dependencies._cached_policy = None
    yield
    print("[clear_policy_cache] Restoring original policy cache state (likely None).")
    dependencies._cached_policy = original_cache  # Restore original (likely None)


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


# --- Test Cases ---


def test_health_check(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# Test with default policy (usually NoOp, determined by .env.test)
# @pytest.mark.envvars({}) # No specific override needed for default
@respx.mock
def test_proxy_with_default_policy(client: TestClient):
    """Test basic proxying with the default policy loaded via env."""
    backend_url = get_test_backend_url()
    mock_route = respx.post(f"{backend_url}/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"id": "chatcmpl-123", "content": "mock response"})
    )
    client_payload = {"model": "test-model", "messages": [{"role": "user", "content": "Hello"}]}
    response = client.post("/v1/chat/completions", json=client_payload, headers={"X-Client-Header": "Value"})

    assert response.status_code == 200
    assert response.json()["id"] == "chatcmpl-123"
    assert mock_route.called
    request_sent = mock_route.calls[0].request
    assert request_sent.headers["x-client-header"] == "Value"
    sent_payload = json.loads(request_sent.content)
    assert sent_payload == client_payload


@pytest.mark.envvars({"POLICY_MODULE": "tests.mocks.policies.ModifyRequestPolicy"})
@respx.mock
def test_proxy_modify_request_policy(client: TestClient):
    """Test policy modifying the request before forwarding."""
    backend_url = get_test_backend_url()
    mock_route = respx.post(f"{backend_url}/modify/req").mock(return_value=httpx.Response(200, text="Backend got it"))
    response = client.post(
        "/modify/req", content=b"original data", headers={"Content-Type": "application/octet-stream"}
    )

    assert response.status_code == 200
    assert response.text == "Backend got it"
    assert mock_route.called
    request_sent = mock_route.calls[0].request
    assert request_sent.headers["x-req-policy"] == "Applied"
    assert request_sent.content == b"original data [REQ_MODIFIED]"


@pytest.mark.envvars({"POLICY_MODULE": "tests.mocks.policies.ModifyResponsePolicy"})
@respx.mock
def test_proxy_modify_response_policy(client: TestClient):
    """Test policy modifying the response from the backend."""
    backend_url = get_test_backend_url()
    mock_route = respx.post(f"{backend_url}/modify/resp").mock(
        return_value=httpx.Response(200, content=b"backend content")
    )
    response = client.post("/modify/resp", content=b"client data", headers={"Content-Type": "application/octet-stream"})

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.content == b"backend content [RESP_MODIFIED]"
    assert response.headers["x-resp-policy"] == "Applied"
    assert mock_route.called


@pytest.mark.envvars({"POLICY_MODULE": "tests.mocks.policies.DirectRequestResponsePolicy"})
@respx.mock
def test_proxy_direct_request_response_policy(client: TestClient):
    """Test policy returning a direct response during request phase."""
    backend_url = get_test_backend_url()
    mock_route = respx.post(f"{backend_url}/direct/req").mock(
        return_value=httpx.Response(200, text="SHOULD NOT BE CALLED")
    )
    response = client.post("/direct/req", content=b"client data", headers={"Content-Type": "application/octet-stream"})

    assert response.status_code == status.HTTP_418_IM_A_TEAPOT
    assert response.content == b"Direct from Request Policy"
    assert not mock_route.called


@pytest.mark.envvars({"POLICY_MODULE": "tests.mocks.policies.DirectResponseResponsePolicy"})
@respx.mock
def test_proxy_direct_response_response_policy(client: TestClient):
    """Test policy returning a direct response during response phase."""
    backend_url = get_test_backend_url()
    mock_route = respx.post(f"{backend_url}/direct/resp").mock(
        return_value=httpx.Response(200, content=b"backend original")
    )
    response = client.post("/direct/resp", content=b"client data", headers={"Content-Type": "application/octet-stream"})

    assert response.status_code == status.HTTP_201_CREATED
    assert response.content == b"Direct from Response Policy"
    assert mock_route.called


@pytest.mark.envvars({"POLICY_MODULE": "tests.mocks.policies.RequestPolicyError"})
@respx.mock
def test_proxy_request_policy_error(client: TestClient):
    """Test handling of error during request policy execution."""
    backend_url = get_test_backend_url()
    mock_route = respx.post(f"{backend_url}/err/req").mock(
        return_value=httpx.Response(200, text="SHOULD NOT BE CALLED")
    )
    response = client.post("/err/req", content=b"client data", headers={"Content-Type": "application/octet-stream"})

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json()["detail"] == "Error applying request policy."
    assert not mock_route.called


@pytest.mark.envvars({"POLICY_MODULE": "tests.mocks.policies.ResponsePolicyError"})
@respx.mock
def test_proxy_response_policy_error(client: TestClient):
    """Test handling of error during response policy execution."""
    backend_url = get_test_backend_url()
    mock_route = respx.post(f"{backend_url}/err/resp").mock(return_value=httpx.Response(200, content=b"backend ok"))
    response = client.post("/err/resp", content=b"client data", headers={"Content-Type": "application/octet-stream"})

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json()["detail"] == "Error applying response policy."
    assert mock_route.called


# Test with default policy (determined by .env.test) again
@respx.mock
def test_proxy_backend_error_passthrough(client: TestClient):
    """Test that backend errors are proxied correctly (if policy doesn't interfere)."""
    backend_url = get_test_backend_url()
    mock_route = respx.post(f"{backend_url}/backend/error").mock(return_value=httpx.Response(503, text="Backend down"))
    response = client.post(
        "/backend/error", content=b"client data", headers={"Content-Type": "application/octet-stream"}
    )
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.text == "Backend down"
    assert mock_route.called


# Test for when BACKEND_URL is invalid in Settings
# This test still needs a specific env var override
@pytest.mark.envvars({"BACKEND_URL": "invalid-url-no-scheme"})
def test_proxy_invalid_backend_url(client: TestClient):
    """Test that an invalid BACKEND_URL in settings causes a 500 error during request."""
    # The envvars marker sets the invalid BACKEND_URL.
    # The request should fail when the Settings dependency is used and validated.
    response = client.post("/some/path", json={"test": "data"})
    # Assert that the application returned a 500 Internal Server Error
    assert response.status_code == 500
    # Optionally, check the detail message if consistent
    assert "Internal server error: Invalid backend configuration." in response.text


# --- Tests for /beta endpoint ---

# Imports needed for /beta tests


@pytest.mark.asyncio
async def test_proxy_endpoint_beta_calls_orchestrator(client: TestClient):
    """Verify /beta endpoint calls run_policy_flow and returns its response."""
    test_path = "/some/beta/path"
    expected_content = b"Response from mocked run_policy_flow"
    expected_status = 201
    # Create a realistic Response object to be returned by the mock
    mock_response = Response(
        content=expected_content,
        status_code=expected_status,
        headers={"X-Mock-Header": "MockValue"},
        media_type="text/plain",
    )

    # Use AsyncMock because run_policy_flow is async
    # Patch the target function within the module where it's *looked up* (server.py)
    with patch("luthien_control.proxy.server.run_policy_flow", new_callable=AsyncMock) as mock_run_flow:
        mock_run_flow.return_value = mock_response

        # Make a request to the /beta endpoint
        actual_response = client.get(f"/beta{test_path}")

    # 1. Assert the response received by the client matches the mock's response
    assert actual_response.status_code == expected_status
    assert actual_response.content == expected_content
    assert actual_response.headers["x-mock-header"] == "MockValue"
    assert actual_response.headers["content-type"].startswith("text/plain")

    # 2. Assert run_policy_flow was called once
    mock_run_flow.assert_awaited_once()

    # 3. Assert run_policy_flow was called with expected argument types
    mock_run_flow.await_args[0]  # Get positional args from the call
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
    assert request_arg.url.path == f"/beta{test_path}"

    # Check dependency types (ensure DI worked)
    assert isinstance(call_kwargs["http_client"], httpx.AsyncClient)
    assert isinstance(call_kwargs["settings"], Settings)
    assert isinstance(call_kwargs["initial_context_policy"], InitializeContextPolicy)
    assert isinstance(call_kwargs["policies"], Sequence)
    # Check that policies sequence contains ControlPolicy instances
    assert all(isinstance(p, ControlPolicy) for p in call_kwargs["policies"])  # Check types if list not empty
    assert isinstance(call_kwargs["builder"], ResponseBuilder)


@pytest.mark.asyncio
async def test_proxy_endpoint_beta_handles_post(client: TestClient):
    """Verify /beta endpoint handles POST requests correctly."""
    test_path = "/some/beta/path/post"
    expected_content = b"Response from mocked run_policy_flow for POST"
    expected_status = 200
    mock_response = Response(content=expected_content, status_code=expected_status)

    with patch("luthien_control.proxy.server.run_policy_flow", new_callable=AsyncMock) as mock_run_flow:
        mock_run_flow.return_value = mock_response

        # Make a POST request to the /beta endpoint
        # Use TestClient directly, no await needed
        response = client.post(f"/beta/proxy{test_path}", content=b"Test POST body")

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
        assert request_arg.url.path == f"/beta/proxy{test_path}"


# --- NEW E2E Test for /beta endpoint ---


@pytest.mark.envvars(
    {
        # Define a simple but representative policy flow for the beta E2E test
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
async def test_beta_proxy_with_simple_flow(client: TestClient):
    """E2E test basic proxying via the /beta endpoint using a defined policy flow."""
    backend_url = get_test_backend_url()
    target_relative_path = "v1/test/beta/endpoint"  # Path expected by backend
    full_backend_url = f"{backend_url}/{target_relative_path}"

    # Mock the final backend call
    mock_route = respx.post(full_backend_url).mock(
        return_value=httpx.Response(200, json={"id": "beta-123", "message": "beta backend response"})
    )

    client_payload = {"data": "value", "other": 123}
    # The path sent to the proxy includes the prefix and the relative path
    proxy_path = f"/beta/{target_relative_path}"

    # Use the TestClient provided by the fixture, which handles async correctly
    response = client.post(proxy_path, json=client_payload, headers={"X-Beta-Test": "true"})

    # async with httpx.AsyncClient(app=client.app, base_url="http://testserver") as async_client:
    #     response = await async_client.post(proxy_path, json=client_payload, headers={"X-Beta-Test": "true"})

    # --- Assertions ---
    # Check final response to client
    assert response.status_code == 200
    assert response.json()["id"] == "beta-123"
    assert response.json()["message"] == "beta backend response"

    # Check backend request
    assert mock_route.called
    assert mock_route.call_count == 1

    request_sent_to_backend = mock_route.calls[0].request

    # Check headers added by policies (PrepareBackendHeadersPolicy)
    assert "x-request-id" in request_sent_to_backend.headers
    assert request_sent_to_backend.headers["x-beta-test"] == "true"  # Original headers preserved
    # Host header should be set correctly by httpx based on target_url
    expected_host = urlparse(backend_url).hostname
    assert request_sent_to_backend.headers["host"] == expected_host

    # Check payload sent to backend (should be unchanged in this flow)
    sent_payload = json.loads(request_sent_to_backend.content)
    assert sent_payload == client_payload
