# tests/proxy/test_server.py
import json
from typing import Sequence
from unittest.mock import AsyncMock, patch, MagicMock
from urllib.parse import urlparse

import httpx
import pytest
import respx
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from luthien_control.config.settings import Settings
from luthien_control.control_policy.initialize_context import InitializeContextPolicy
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.core.response_builder.interface import ResponseBuilder
from luthien_control.main import app  # Import your main FastAPI app
from fastapi.responses import PlainTextResponse
from luthien_control.dependencies import (
    get_control_policies,
    get_http_client,
    get_initial_context_policy,
    get_response_builder,
)

# --- Pytest Fixtures ---


@pytest.fixture
def test_app() -> FastAPI:
    """Returns the FastAPI app instance for testing."""
    # Ensure dependency overrides are cleared - IMPORTANT for clean test state
    # Although we aim not to use overrides, this is a safeguard.
    app.dependency_overrides = {}
    return app


# ignore type check here, this is a valid use case for a pytest fixture
@pytest.fixture
def client(test_app: FastAPI) -> TestClient:  # type: ignore[misc]
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


# --- Tests for /api endpoint ---


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
    assert request_arg.url.path == f"/api/{test_path}"

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
    assert request_arg.url.path == f"/api/{test_path}"

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
async def test_api_proxy_with_simple_flow(test_app: FastAPI, client: TestClient):
    """E2E test basic proxying via the /api endpoint using a defined policy flow."""
    backend_url = get_test_backend_url()
    target_relative_path = "v1/test/api/endpoint"  # Path expected by backend
    full_backend_url = f"{backend_url}/{target_relative_path}"

    # Mock the final backend call
    mock_route = respx.post(full_backend_url).mock(
        return_value=httpx.Response(200, json={"id": "api-123", "message": "api backend response"})
    )

    client_payload = {"data": "value", "other": 123}
    # The path sent to the proxy includes the prefix and the relative path
    proxy_path = f"/api/{target_relative_path}"

    # Add auth header for the E2E style test client request
    auth_headers = {"Authorization": "Bearer test-e2e-key"}

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
    assert json.loads(request_sent_to_backend.content.decode("utf-8")) == client_payload


# --- NEW Integration Tests for Control Policy Loading ---

# Note: These tests use the /api/health endpoint as a simple target
#       to trigger the dependency resolution, specifically the loading
#       of control policies via get_control_policies. We are primarily
#       interested in whether the *loading* succeeds or fails based on
#       the CONTROL_POLICIES environment variable, not the endpoint's own logic.


@pytest.mark.envvars(
    {
        "CONTROL_POLICIES": (
            "tests.helpers.dummy_policies.DummyPolicyNoArgs, tests.helpers.dummy_policies.DummyPolicySettings"
        )
    }
)
@pytest.mark.asyncio
async def test_integration_policy_loading_success(test_app: FastAPI, client: TestClient):
    """Integration Test: Verify successful loading of valid control policies via endpoint dependency."""

    # Mock the response builder to return a simple 200 OK, isolating the test to policy loading
    mock_builder_instance = MagicMock(spec=ResponseBuilder)
    mock_builder_instance.build_response.return_value = PlainTextResponse("OK", status_code=200)

    def get_mock_builder():
        return mock_builder_instance

    test_app.dependency_overrides[get_response_builder] = get_mock_builder

    # Target an endpoint that uses the get_control_policies dependency
    # The specific response content doesn't matter now, just the status code
    response = client.get("/api/health", headers={"Authorization": "Bearer test"})

    # Clean up overrides after the test
    test_app.dependency_overrides = {}

    # If loading failed, get_control_policies would raise HTTPException(500)
    # If loading succeeded, our mock builder returns 200
    assert response.status_code == 200


@pytest.mark.envvars({"CONTROL_POLICIES": ""})
@pytest.mark.asyncio
async def test_integration_policy_loading_empty_string(test_app: FastAPI, client: TestClient):
    """Integration Test: Verify behavior when CONTROL_POLICIES is empty."""
    response = client.get("/api/health", headers={"Authorization": "Bearer test"})
    test_app.dependency_overrides = {}
    # Expect 500 because policy loading succeeds (empty list), but no policy runs
    # to set a final status, so the DefaultResponseBuilder defaults to 500.
    assert response.status_code == 500
    # Optional: Check detail to confirm it's the expected builder error
    # assert "No backend response or final_status_code found" in response.json().get("detail", "")


@pytest.mark.envvars({"CONTROL_POLICIES": "invalid.path.DoesNotExist"})
@pytest.mark.asyncio
async def test_integration_policy_loading_invalid_path(test_app: FastAPI, client: TestClient):
    """Integration Test: Verify 500 error when CONTROL_POLICIES contains an invalid module path."""
    response = client.get("/api/health", headers={"Authorization": "Bearer test"})
    test_app.dependency_overrides = {}
    assert response.status_code == 500
    assert "Could not load policy class 'invalid.path.DoesNotExist'" in response.json()["detail"]


@pytest.mark.envvars({"CONTROL_POLICIES": "tests.helpers.dummy_policies.NonExistentClass"})
@pytest.mark.asyncio
async def test_integration_policy_loading_class_not_found(test_app: FastAPI, client: TestClient):
    """Integration Test: Verify 500 error when CONTROL_POLICIES points to a non-existent class in a valid module."""
    response = client.get("/api/health", headers={"Authorization": "Bearer test"})
    test_app.dependency_overrides = {}
    assert response.status_code == 500
    assert "Could not load policy class 'tests.helpers.dummy_policies.NonExistentClass'" in response.json()["detail"]


@pytest.mark.envvars({"CONTROL_POLICIES": "tests.helpers.dummy_policies.InvalidPolicyNotSubclass"})
@pytest.mark.asyncio
async def test_integration_policy_loading_not_subclass(test_app: FastAPI, client: TestClient):
    """Integration Test: Verify 500 error when policy class doesn't inherit from ControlPolicy."""
    response = client.get("/api/health", headers={"Authorization": "Bearer test"})
    test_app.dependency_overrides = {}
    assert response.status_code == 500
    assert "does not inherit from ControlPolicy" in response.json()["detail"]
    assert "'InvalidPolicyNotSubclass'" in response.json()["detail"]


@pytest.mark.envvars({"CONTROL_POLICIES": "tests.helpers.dummy_policies.DummyPolicyNeedsSpecificArg"})
@pytest.mark.asyncio
async def test_integration_policy_loading_instantiation_error(test_app: FastAPI, client: TestClient):
    """Integration Test: Verify 500 error when policy instantiation fails due to missing __init__ args."""
    response = client.get("/api/health", headers={"Authorization": "Bearer test"})
    test_app.dependency_overrides = {}
    assert response.status_code == 500
    # The error message checks if specific args were attempted based on signature inspection
    # In this case, signature inspection finds no known args (settings/http_client), so it tries no-arg fallback
    assert "Could not instantiate policy class 'DummyPolicyNeedsSpecificArg'" in response.json()["detail"]
    assert "Check __init__ signature" in response.json()["detail"]


@pytest.mark.envvars({"CONTROL_POLICIES": "tests.helpers.dummy_policies.DummyPolicyInitRaises"})
@pytest.mark.asyncio
async def test_integration_policy_loading_init_raises_error(test_app: FastAPI, client: TestClient):
    """Integration Test: Verify 500 error when policy __init__ raises an exception."""
    response = client.get("/api/health", headers={"Authorization": "Bearer test"})
    test_app.dependency_overrides = {}
    assert response.status_code == 500
    assert "Unexpected error loading policy" in response.json()["detail"]
    assert "Deliberate init failure" in response.json()["detail"]
