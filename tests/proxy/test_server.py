# tests/proxy/test_server.py
import json
from unittest.mock import AsyncMock, MagicMock, patch
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
from luthien_control.dependencies import (
    get_initial_context_policy,
    get_main_control_policy,
    get_response_builder,
)
from luthien_control.main import app  # Import your main FastAPI app

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


@pytest.fixture
def mock_main_policy_for_simple_tests() -> AsyncMock:
    """Provides a basic mock policy for tests that just need the dependency met."""
    return AsyncMock(spec=ControlPolicy, name="MockMainPolicySimple")


@pytest.mark.asyncio
async def test_api_proxy_endpoint_calls_orchestrator(
    test_app: FastAPI, client: TestClient, mock_main_policy_for_simple_tests: AsyncMock
):
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

    # --- Override main policy dependency --- #
    async def override_get_main_policy():
        return mock_main_policy_for_simple_tests

    test_app.dependency_overrides[get_main_control_policy] = override_get_main_policy
    # --- End Override --- #

    with patch("luthien_control.proxy.server.run_policy_flow", new_callable=AsyncMock) as mock_run_flow:
        mock_run_flow.return_value = mock_response

        # Make a request to the /api endpoint with auth header
        actual_response = client.get(f"/api/{test_path}", headers=auth_headers)

    # Clean up override AFTER request
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
    assert "main_policy" in call_kwargs
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
    assert isinstance(call_kwargs["main_policy"], ControlPolicy)
    assert isinstance(call_kwargs["builder"], ResponseBuilder)

    # Verify the auth header was received by the endpoint
    assert request_arg.headers.get("authorization") == "Bearer test-key"


@pytest.mark.asyncio
async def test_api_proxy_endpoint_handles_post(
    test_app: FastAPI, client: TestClient, mock_main_policy_for_simple_tests: AsyncMock
):
    """Verify /api endpoint handles POST requests correctly."""
    test_path = "some/api/path/post"
    expected_content = b"Response from mocked run_policy_flow for POST"
    expected_status = 200
    mock_response = Response(content=expected_content, status_code=expected_status)
    auth_headers = {"Authorization": "Bearer test-key-post"}

    # --- Override main policy dependency --- #
    async def override_get_main_policy():
        return mock_main_policy_for_simple_tests

    test_app.dependency_overrides[get_main_control_policy] = override_get_main_policy
    # --- End Override --- #

    with patch("luthien_control.proxy.server.run_policy_flow", new_callable=AsyncMock) as mock_run_flow:
        mock_run_flow.return_value = mock_response

        # Make a POST request to the /api endpoint with auth header
        response = client.post(f"/api/{test_path}", content=b"Test POST body", headers=auth_headers)

    # Clean up override AFTER request
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


# --- Integration Test for /api endpoint with Mocked Main Policy ---


@pytest.fixture
def mock_main_policy_for_e2e() -> ControlPolicy:
    """Provides a mock policy simulating the necessary actions for the E2E test."""
    # In a real scenario, this might be a CompoundPolicy mock or similar
    # For this test, we just need *a* policy that eventually triggers the backend call
    # The actual policy logic (header prep, request sending) is implicitly tested
    # by mocking the run_policy_flow or, more accurately, by letting the real endpoint
    # use its dependencies which include the *real* policies loaded by the mocked
    # get_main_control_policy.
    # Let's assume the flow involves PrepareBackendHeadersPolicy and SendBackendRequestPolicy.
    # Instead of mocking them individually, we provide a single mock ControlPolicy
    # for the get_main_control_policy dependency override.
    # The test then relies on run_policy_flow (unmocked) calling this policy's apply.
    # For simplicity here, we return a basic mock. A more robust test might mock
    # load_policy_instance within get_main_control_policy or mock the DB directly.

    # Let's create a simple passthrough mock policy for the dependency override.
    # The key is that the endpoint uses this dependency.
    mock_policy = AsyncMock(spec=ControlPolicy)

    async def apply_effect(context):
        # Simulate the policy flow leading to a backend request being set
        # In a real test of the *new* loading, we wouldn't mock this deeply,
        # but test that the correct DB-loaded policy executes.
        # For *this* specific test refactoring, we just need to ensure the endpoint
        # uses the mocked dependency and the rest of the flow (like backend call)
        # works.

        # Check if http_client is in context (it should be added by run_policy_flow)
        if not context.http_client:
            raise RuntimeError("http_client not found in context for mock policy")

        backend_url = get_test_backend_url()
        target_relative_path = "v1/test/api/endpoint"  # Must match the test path

        # Pass original headers from the client request, EXCLUDING Host
        headers_to_send = {
            k.decode(): v.decode() for k, v in context.fastapi_request.headers.raw if k.lower() != b"host"
        }

        context.backend_request = httpx.Request(
            method="POST",
            url=f"{backend_url}/{target_relative_path}",
            headers=headers_to_send,  # Let httpx handle the Host header based on URL
            content=await context.fastapi_request.body(),
        )
        # PrepareBackendHeadersPolicy would add x-request-id here
        context.backend_request.headers["x-request-id"] = "mock-test-id"
        # SendBackendRequestPolicy would make the call and set the response
        # Simulate SendBackendRequestPolicy making the call and storing the response
        try:
            backend_response = await context.http_client.send(context.backend_request)
            context.backend_response = backend_response
            # Ensure content is read if needed by the builder later
            # await context.backend_response.aread()
        except Exception as e:
            # Handle potential exceptions during the mocked send if needed
            print(f"Error in mock policy sending request: {e}")
            context.exception = e

        return context

    mock_policy.apply = apply_effect
    mock_policy.name = "MockE2EPolicyFlow"
    return mock_policy


@respx.mock
@pytest.mark.asyncio  # TestClient handles async endpoint, but mark test for clarity
async def test_api_proxy_with_mocked_policy_flow(
    test_app: FastAPI,
    client: TestClient,
    mock_main_policy_for_e2e: ControlPolicy,  # Use the new fixture
    mock_initial_policy: InitializeContextPolicy,  # Re-use existing mock fixture
    mock_builder: ResponseBuilder,  # Re-use existing mock fixture
):
    """Integration test for /api endpoint, mocking the main policy dependency."""
    backend_url = get_test_backend_url()
    target_relative_path = "v1/test/api/endpoint"  # Path expected by backend
    full_backend_url = f"{backend_url}/{target_relative_path}"

    # Mock the final backend call
    mock_route = respx.post(full_backend_url).mock(
        return_value=httpx.Response(200, json={"id": "mock-flow-123", "message": "mock flow backend response"})
    )

    client_payload = {"data": "value", "other": 123}
    # The path sent to the proxy includes the prefix and the relative path
    proxy_path = f"/api/{target_relative_path}"

    # --- Override Dependencies --- #
    # Override the main policy loader to return our specific mock policy
    # This replaces the old CONTROL_POLICIES mechanism for this test
    async def override_get_main_policy():
        return mock_main_policy_for_e2e

    # Override other dependencies if needed, or use mocks from fixtures
    def override_get_initial_policy():
        return mock_initial_policy

    def override_get_builder():
        # Use a simple builder that passes backend response through
        builder = MagicMock(spec=ResponseBuilder)

        def build_response(context, exception=None):
            if context.backend_response:
                return Response(
                    content=context.backend_response.content,
                    status_code=context.backend_response.status_code,
                    headers=dict(context.backend_response.headers),
                    media_type=context.backend_response.headers.get("content-type"),
                )
            return Response(content=b"Builder Fallback", status_code=500)

        builder.build_response = build_response
        return builder

    test_app.dependency_overrides[get_main_control_policy] = override_get_main_policy
    test_app.dependency_overrides[get_initial_context_policy] = override_get_initial_policy
    test_app.dependency_overrides[get_response_builder] = override_get_builder
    # We don't override get_http_client, letting the TestClient manage it
    # --- End Override Dependencies --- #

    # Make the request
    response = client.post(proxy_path, json=client_payload, headers={"X-API-Test": "true"})

    # Clean up overrides *after* the request
    test_app.dependency_overrides = {}

    # --- Assertions ---
    # Check final response to client
    assert response.status_code == 200
    assert response.json()["id"] == "mock-flow-123"
    assert response.json()["message"] == "mock flow backend response"

    # Check backend request
    assert mock_route.called
    assert mock_route.call_count == 1

    request_sent_to_backend = mock_route.calls[0].request

    # Check headers added by policies (PrepareBackendHeadersPolicy)
    assert "x-request-id" in request_sent_to_backend.headers
    assert request_sent_to_backend.headers["x-api-test"] == "true"  # Original headers preserved
    # Host header should include port if it's non-standard
    expected_netloc = urlparse(backend_url).netloc
    assert request_sent_to_backend.headers["host"] == expected_netloc

    # Check payload sent to backend (should be unchanged in this flow)
    assert json.loads(request_sent_to_backend.content.decode("utf-8")) == client_payload
