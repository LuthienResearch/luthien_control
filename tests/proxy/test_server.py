# tests/proxy/test_server.py
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from luthien_control.config.settings import Settings
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.core.response_builder.interface import ResponseBuilder
from luthien_control.dependencies import (
    get_main_control_policy,
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
    # Patch DB engine/pool creation during TestClient lifespan
    # to prevent slow/failing startup in tests.
    with (
        patch("luthien_control.db.database_async.create_db_engine", new_callable=AsyncMock) as mock_create_main_engine,
    ):  # Patch the actual creation functions
        # Ensure mocked functions return a mock engine/pool or None to simulate success/failure
        # Returning None should be sufficient to bypass actual DB connection attempts.
        mock_create_main_engine.return_value = None  # Or AsyncMock() if needed later

        # Now instantiate the TestClient *while the patches are active*
        with TestClient(test_app) as test_client:
            yield test_client  # Yield the client for tests to use
    # Patches are automatically removed when the 'with patch(...)' block exits


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
    assert "main_policy" in call_kwargs
    assert "builder" in call_kwargs

    # Check request object details
    request_arg = call_kwargs["request"]
    assert isinstance(request_arg, Request)
    assert request_arg.method == "GET"
    # TestClient uses http://testserver as base URL
    assert request_arg.url.path == f"/api/{test_path}"

    # Check dependency types (ensure DI worked)
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

        get_test_backend_url()

        # Pass original headers from the client request, EXCLUDING Host
        {k.decode(): v.decode() for k, v in context.fastapi_request.headers.raw if k.lower() != b"host"}

        return context

    mock_policy.apply = apply_effect
    mock_policy.name = "MockE2EPolicyFlow"
    return mock_policy


# TODO: write integration tests for the /api endpoint with a real policy
