# tests/proxy/test_server.py
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependencies import (
    get_main_control_policy,
)
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction_context import TransactionContext
from luthien_control.main import app  # Import your main FastAPI app
from luthien_control.settings import Settings
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

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
    """Provides a FastAPI test client that correctly handles lifespan events by mocking DB dependencies."""
    mock_engine_instance = AsyncMock(spec=AsyncEngine)

    # This factory, when called, will produce mock_session_instance
    mock_sa_session_factory_instance = MagicMock(spec=async_sessionmaker)
    mock_session_instance = AsyncMock(spec=AsyncSession)
    mock_sa_session_factory_instance.return_value = mock_session_instance

    async def mock_create_db_engine_side_effect(*args, **kwargs):
        # This is called by _initialize_app_dependencies.
        # It needs to return a truthy engine object.
        return mock_engine_instance

    # Patch create_db_engine: it's called by _initialize_app_dependencies.
    # Patch _db_session_factory: it's used by get_db_session (which is in database_async.py itself)
    # and _initialize_app_dependencies gets a reference to this get_db_session.
    with (
        patch(
            "luthien_control.db.database_async.create_db_engine",
            new_callable=AsyncMock,
            side_effect=mock_create_db_engine_side_effect,
        ),
        patch("luthien_control.db.database_async._db_session_factory", new=mock_sa_session_factory_instance),
    ):
        # Now, when _initialize_app_dependencies runs during TestClient setup:
        # 1. `await create_db_engine()` returns `mock_engine_instance`. The `if not db_engine:` check passes.
        #    Crucially, the real create_db_engine() which sets _db_session_factory is *not* run.
        # 2. `db_session_factory = get_db_session` (in _initialize_app_dependencies).
        #    `get_db_session` (from database_async.py) will now use our patched `_db_session_factory`.
        #    So `db_session_factory()` will produce `mock_session_instance`.
        # 3. `DependencyContainer` is created with `http_client` (real, from original _initialize_app_dependencies),
        #    `settings` (real), and `db_session_factory` (our mock factory).
        # Lifespan completes. app.state.dependencies becomes a "real" container instance with properly mocked DB parts.
        with TestClient(test_app) as test_client:
            yield test_client
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
    test_app: FastAPI,
    mocker,
    mock_container: MagicMock,
    mock_main_policy_for_simple_tests: AsyncMock,
):
    """Verify /api POST endpoint calls run_policy_flow, handles JSON body, and returns its response."""
    test_path = "some/api/path/post"
    expected_content = b"Response from mocked run_policy_flow for POST"
    expected_status = 200
    mock_response_obj = Response(
        content=expected_content,
        status_code=expected_status,
        headers={"X-Mock-Header": "MockValue"},
        media_type="application/json",
    )
    auth_headers = {"Authorization": "Bearer test-key-post"}
    request_body = {"test": "body"}

    # --- Mock _initialize_app_dependencies to return our mock_container --- #
    mocker.patch(
        "luthien_control.main._initialize_app_dependencies", new_callable=AsyncMock, return_value=mock_container
    )

    # --- Override main policy dependency (still valid) --- #
    async def override_get_main_policy():
        return mock_main_policy_for_simple_tests

    test_app.dependency_overrides[get_main_control_policy] = override_get_main_policy
    # --- End Setup --- #

    # Instantiate TestClient here, after the relevant patches are active.
    with TestClient(test_app) as client_instance:
        # At this point, app.state.dependencies should be mock_container
        assert hasattr(client_instance.app.state, "dependencies")
        assert client_instance.app.state.dependencies is mock_container, (
            "app.state.dependencies was not the mock_container after TestClient instantiation"
        )

        with patch("luthien_control.proxy.server.run_policy_flow", new_callable=AsyncMock) as mock_run_flow:
            mock_run_flow.return_value = mock_response_obj
            response = client_instance.post(f"/api/{test_path}", json=request_body, headers=auth_headers)

    test_app.dependency_overrides = {}  # Clear overrides

    # 1. Assert the response received by the client matches the mock's response
    assert response.status_code == expected_status
    assert response.content == expected_content
    assert response.headers["x-mock-header"] == "MockValue"
    assert response.headers["content-type"].startswith("application/json")

    # 2. Assert run_policy_flow was called once
    mock_run_flow.assert_awaited_once()

    # 3. Assert run_policy_flow was called with expected arguments
    call_kwargs = mock_run_flow.await_args[1]
    assert "request" in call_kwargs
    assert "main_policy" in call_kwargs
    assert "dependencies" in call_kwargs
    assert "session" in call_kwargs

    assert call_kwargs["dependencies"] is mock_container
    assert call_kwargs["main_policy"] is mock_main_policy_for_simple_tests

    request_arg = call_kwargs["request"]
    assert isinstance(request_arg, Request)
    assert request_arg.method == "POST"
    assert request_arg.url.path == f"/api/{test_path}"
    assert request_arg.headers.get("authorization") == "Bearer test-key-post"
    # Add assertion for request body if needed (it was read by run_policy_flow)
    # body = await request_arg.json() # Need await inside async context
    # assert body == request_body


@pytest.mark.asyncio
async def test_api_proxy_get_endpoint_calls_orchestrator(
    test_app: FastAPI,
    mocker,
    mock_container: MagicMock,
    mock_main_policy_for_simple_tests: AsyncMock,
):
    """Verify /api GET endpoint calls run_policy_flow and returns its response."""
    test_path = "some/api/path/get"
    expected_content = b"Response from mocked run_policy_flow for GET"
    expected_status = 200
    mock_response_obj = Response(
        content=expected_content,
        status_code=expected_status,
        headers={"X-Mock-Header": "MockValueGet"},
        media_type="application/json",
    )
    auth_headers = {"Authorization": "Bearer test-key-get"}

    # --- Mock _initialize_app_dependencies to return our mock_container --- #
    mocker.patch(
        "luthien_control.main._initialize_app_dependencies", new_callable=AsyncMock, return_value=mock_container
    )

    # --- Override main policy dependency (still valid) --- #
    async def override_get_main_policy():
        return mock_main_policy_for_simple_tests

    test_app.dependency_overrides[get_main_control_policy] = override_get_main_policy
    # --- End Setup --- #

    # Instantiate TestClient here, after the relevant patches are active.
    with TestClient(test_app) as client_instance:
        assert hasattr(client_instance.app.state, "dependencies")
        assert client_instance.app.state.dependencies is mock_container

        with patch("luthien_control.proxy.server.run_policy_flow", new_callable=AsyncMock) as mock_run_flow:
            mock_run_flow.return_value = mock_response_obj
            response = client_instance.get(f"/api/{test_path}", headers=auth_headers)

    test_app.dependency_overrides = {}  # Clear overrides

    # 1. Assert the response received by the client matches the mock's response
    assert response.status_code == expected_status
    assert response.content == expected_content
    assert response.headers["x-mock-header"] == "MockValueGet"
    assert response.headers["content-type"].startswith("application/json")

    # 2. Assert run_policy_flow was called once
    mock_run_flow.assert_awaited_once()

    # 3. Assert run_policy_flow was called with expected arguments
    call_kwargs = mock_run_flow.await_args[1]
    assert "request" in call_kwargs
    assert "main_policy" in call_kwargs
    assert "dependencies" in call_kwargs
    assert "session" in call_kwargs

    assert call_kwargs["dependencies"] is mock_container
    assert call_kwargs["main_policy"] is mock_main_policy_for_simple_tests

    request_arg = call_kwargs["request"]
    assert isinstance(request_arg, Request)
    assert request_arg.method == "GET"
    assert request_arg.url.path == f"/api/{test_path}"
    assert request_arg.headers.get("authorization") == "Bearer test-key-get"


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
        context.data["passthrough_applied"] = True
        return context

    def serialize(self) -> SerializableDict:
        return {}

    @classmethod
    def from_serialized(cls, config: SerializableDict, **kwargs) -> "PassThroughPolicy":
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
    def from_serialized(cls, config: SerializableDict, **kwargs) -> "MockSendBackendRequestPolicy":
        # Not needed for this test, but must be implemented
        # For a real policy, you'd use config.
        raise NotImplementedError


@pytest.mark.asyncio
async def test_api_proxy_no_auth_policy_no_key_success(
    test_app: FastAPI,
    mocker: MagicMock,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """
    Verify that requests without an API key succeed when the main policy
    (e.g., NoOpPolicy) does not require authentication.
    This uses dependency overrides and mocks the backend HTTP call via policy.
    """
    test_path = "v1/models"
    backend_response_content = {"detail": "Success from mocked backend via policy"}
    mock_backend_httpx_response = httpx.Response(200, json=backend_response_content, headers={"X-Backend-Mock": "true"})

    mock_container.http_client.request = AsyncMock(return_value=mock_backend_httpx_response)

    mocker.patch(
        "luthien_control.main._initialize_app_dependencies", new_callable=AsyncMock, return_value=mock_container
    )

    main_test_policy = MockSendBackendRequestPolicy(mock_response=mock_backend_httpx_response)

    async def override_get_main_policy():
        return main_test_policy

    test_app.dependency_overrides[get_main_control_policy] = override_get_main_policy

    # Instantiate TestClient here, after patches are active
    with TestClient(test_app) as client_instance:
        # Check app.state.dependencies immediately
        assert hasattr(client_instance.app.state, "dependencies")
        assert client_instance.app.state.dependencies is mock_container, (
            "app.state.dependencies was not mock_container after TestClient instantiation"
        )

        # For a POST, we might need a json body, even if empty or None, depending on policy.
        # Let's assume for a generic policy test, an empty JSON body is acceptable if no specific body is needed.
        response = client_instance.post(f"/api/{test_path}", json=None)

    test_app.dependency_overrides = {}  # Clear overrides

    assert response.status_code == 200
    assert response.json() == backend_response_content
    assert response.headers["x-backend-mock"] == "true"
    # Check if the backend mock on the container's client was called if your policy uses it.
    # If main_test_policy uses container.http_client.request(...):
    # This depends on the implementation of main_test_policy. The current MockSendBackendRequestPolicy
    # directly sets the response, so it does not call http_client.request itself.


# TODO: write integration tests for the /api endpoint with a real policy


def test_api_proxy_explicit_options_handler(client: TestClient):
    """Test that the explicit OPTIONS handler for /api returns correct headers."""
    test_path = "some/api/path/options"
    response = client.options(f"/api/{test_path}")

    assert response.status_code == 200
    assert response.text == ""  # OPTIONS handlers typically have no body
    assert response.headers["allow"] == "GET, POST, OPTIONS"
    assert response.headers["access-control-allow-origin"] == "*"
    assert response.headers["access-control-allow-methods"] == "GET, POST, OPTIONS"
    assert response.headers["access-control-allow-headers"] == "Authorization, Content-Type"
