# tests/proxy/test_server.py
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from luthien_control.control_policy.compound_policy import CompoundPolicy
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependencies import (
    get_db_session,
    get_dependencies,
    get_main_control_policy,
)
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction_context import TransactionContext
from luthien_control.main import app  # Import your main FastAPI app
from luthien_control.settings import Settings
from sqlalchemy.ext.asyncio import AsyncSession

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
async def test_api_proxy_post_endpoint_calls_orchestrator(
    test_app: FastAPI, client: TestClient, mock_container: MagicMock, mock_main_policy_for_simple_tests: AsyncMock
):
    """Verify /api POST endpoint calls run_policy_flow, handles JSON body, and returns its response."""
    test_path = "some/api/path/post"
    expected_content = b"Response from mocked run_policy_flow for POST"
    expected_status = 200
    # Add headers to the mock response for assertions
    mock_response = Response(
        content=expected_content,
        status_code=expected_status,
        headers={"X-Mock-Header": "MockValue"},
        media_type="application/json",  # Match common API responses
    )
    auth_headers = {"Authorization": "Bearer test-key-post"}
    request_body = {"test": "body"}

    # --- Override container and main policy dependencies --- #
    def override_get_container():
        mock_container.settings.get_top_level_policy_name.return_value = "mock-post-policy"
        return mock_container

    test_app.dependency_overrides[get_dependencies] = override_get_container

    async def override_get_main_policy():
        return mock_main_policy_for_simple_tests

    test_app.dependency_overrides[get_main_control_policy] = override_get_main_policy
    # --- End Setup --- #

    with patch("luthien_control.proxy.server.run_policy_flow", new_callable=AsyncMock) as mock_run_flow:
        mock_run_flow.return_value = mock_response
        response = client.post(f"/api/{test_path}", json=request_body, headers=auth_headers)

    test_app.dependency_overrides = {}  # Clear overrides

    # 1. Assert the response received by the client matches the mock's response
    assert response.status_code == expected_status
    assert response.content == expected_content
    # Add header assertions from the removed test
    assert response.headers["x-mock-header"] == "MockValue"
    assert response.headers["content-type"].startswith("application/json")

    # 2. Assert run_policy_flow was called once
    mock_run_flow.assert_awaited_once()

    # 3. Assert run_policy_flow was called with expected arguments
    call_kwargs = mock_run_flow.await_args[1]
    assert "request" in call_kwargs
    assert "main_policy" in call_kwargs
    assert "dependencies" in call_kwargs
    # Add session assertion from the removed test
    assert "session" in call_kwargs

    assert call_kwargs["dependencies"] is mock_container
    assert call_kwargs["main_policy"] is mock_main_policy_for_simple_tests
    # Add session type check
    assert isinstance(call_kwargs["session"], AsyncMock)

    request_arg = call_kwargs["request"]
    assert isinstance(request_arg, Request)
    assert request_arg.method == "POST"
    assert request_arg.url.path == f"/api/{test_path}"
    assert request_arg.headers.get("authorization") == "Bearer test-key-post"
    # Add assertion for request body if needed (it was read by run_policy_flow)
    # body = await request_arg.json() # Need await inside async context
    # assert body == request_body


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


# --- Integration-style Tests for /api endpoint ---


# Define a minimal concrete policy locally for the test
class PassThroughPolicy(ControlPolicy):
    async def apply(
        self, context: TransactionContext, container: DependencyContainer, session: AsyncSession
    ) -> TransactionContext:
        return context  # Does nothing, just passes through

    def serialize(self) -> SerializableDict:
        return {}

    @classmethod
    async def from_serialized(cls, config: SerializableDict, **kwargs) -> "PassThroughPolicy":
        return cls()


# Define a second minimal policy that just sets the response
class MockSendBackendRequestPolicy(ControlPolicy):
    def __init__(self, mock_response: httpx.Response):
        self.mock_response = mock_response
        self.name = self.__class__.__name__

    async def apply(
        self, context: TransactionContext, container: DependencyContainer, session: AsyncSession
    ) -> TransactionContext:
        # Simulate setting the response after a backend call
        context.response = self.mock_response
        return context

    def serialize(self) -> SerializableDict:
        # Not needed for this test
        return {}

    @classmethod
    async def from_serialized(cls, config: SerializableDict, **kwargs) -> "MockSendBackendRequestPolicy":
        # Not needed for this test
        raise NotImplementedError


@pytest.mark.asyncio
async def test_api_proxy_no_auth_policy_no_key_success(
    test_app: FastAPI,
    client: TestClient,
    mock_container: MagicMock,  # Re-use existing fixture
    mock_db_session: AsyncMock,  # Use the correct fixture
):
    """
    Verify that requests without an API key succeed when the main policy
    (e.g., NoOpPolicy) does not require authentication.
    This uses dependency overrides and mocks the backend HTTP call via policy.
    """
    test_path = "v1/models"
    backend_target_url = f"{get_test_backend_url()}/{test_path}"
    expected_backend_response_data = {"data": [{"id": "model-1"}]}
    # This httpx.Response will be placed in context.response by the mock policy
    mock_http_response = httpx.Response(
        200, json=expected_backend_response_data, request=httpx.Request("GET", backend_target_url)
    )

    # --- Setup Dependencies & Mocks --- #

    # 1. Override get_dependencies (only needed for settings if policy uses it)
    def override_get_container():
        mock_container.settings.get_backend_url.return_value = get_test_backend_url()
        mock_container.settings.get_top_level_policy_name.return_value = "TestCompoundPolicy"
        return mock_container

    test_app.dependency_overrides[get_dependencies] = override_get_container

    # 2. Override get_main_control_policy to return a CompoundPolicy
    async def override_get_main_policy():
        mock_sender = MockSendBackendRequestPolicy(mock_response=mock_http_response)
        return CompoundPolicy(policies=[PassThroughPolicy(), mock_sender], name="TestCompoundPolicy")

    test_app.dependency_overrides[get_main_control_policy] = override_get_main_policy

    # 3. Override get_db_session to return a mock session
    async def override_get_session():
        return mock_db_session

    test_app.dependency_overrides[get_db_session] = override_get_session

    # --- Make Request (No Authorization Header) --- #
    actual_response = client.post(f"/api/{test_path}")

    # --- Clean Up Overrides --- #
    test_app.dependency_overrides = {}

    # --- Assertions --- #
    assert actual_response.status_code == 200
    assert actual_response.json() == expected_backend_response_data


# TODO: write integration tests for the /api endpoint with a real policy
