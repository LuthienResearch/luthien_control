# tests/proxy/test_server.py
import json  # Add json import

import httpx
import pytest
import respx
from fastapi import FastAPI, status  # Alias Starlette Response
from fastapi.testclient import TestClient
from luthien_control.config.settings import Settings
from luthien_control.main import app  # Import your main FastAPI app

# --- REMOVED Mock Policy Implementations ---
# (Moved to luthien_control/testing/mocks/policies.py)

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
    dependencies._cached_policy = original_cache # Restore original (likely None)

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
        return url.rstrip('/') # Ensure no trailing slash for respx
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
    # REMOVED: del app.dependency_overrides[get_policy]


@pytest.mark.envvars({"POLICY_MODULE": "luthien_control.testing.mocks.policies.ModifyRequestPolicy"})
@respx.mock
def test_proxy_modify_request_policy(client: TestClient):
    """Test policy modifying the request before forwarding."""
    backend_url = get_test_backend_url()
    mock_route = respx.post(f"{backend_url}/modify/req").mock(
        return_value=httpx.Response(200, text="Backend got it")
    )
    response = client.post(
        "/modify/req", content=b"original data", headers={"Content-Type": "application/octet-stream"}
    )

    assert response.status_code == 200
    assert response.text == "Backend got it"
    assert mock_route.called
    request_sent = mock_route.calls[0].request
    assert request_sent.headers["x-req-policy"] == "Applied"
    assert request_sent.content == b"original data [REQ_MODIFIED]"
    # REMOVED: del app.dependency_overrides[get_policy]


@pytest.mark.envvars({"POLICY_MODULE": "luthien_control.testing.mocks.policies.ModifyResponsePolicy"})
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
    # REMOVED: del app.dependency_overrides[get_policy]


@pytest.mark.envvars({"POLICY_MODULE": "luthien_control.testing.mocks.policies.DirectRequestResponsePolicy"})
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
    # REMOVED: del app.dependency_overrides[get_policy]


@pytest.mark.envvars({"POLICY_MODULE": "luthien_control.testing.mocks.policies.DirectResponseResponsePolicy"})
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
    # REMOVED: del app.dependency_overrides[get_policy]


@pytest.mark.envvars({"POLICY_MODULE": "luthien_control.testing.mocks.policies.RequestPolicyError"})
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
    # REMOVED: del app.dependency_overrides[get_policy]


@pytest.mark.envvars({"POLICY_MODULE": "luthien_control.testing.mocks.policies.ResponsePolicyError"})
@respx.mock
def test_proxy_response_policy_error(client: TestClient):
    """Test handling of error during response policy execution."""
    backend_url = get_test_backend_url()
    mock_route = respx.post(f"{backend_url}/err/resp").mock(
        return_value=httpx.Response(200, content=b"backend ok")
    )
    response = client.post("/err/resp", content=b"client data", headers={"Content-Type": "application/octet-stream"})

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json()["detail"] == "Error applying response policy."
    assert mock_route.called
    # REMOVED: del app.dependency_overrides[get_policy]


# Test with default policy (determined by .env.test) again
@respx.mock
def test_proxy_backend_error_passthrough(client: TestClient):
    """Test that backend errors are proxied correctly (if policy doesn't interfere)."""
    backend_url = get_test_backend_url()
    mock_route = respx.post(f"{backend_url}/backend/error").mock(
        return_value=httpx.Response(503, text="Backend down")
    )
    response = client.post(
        "/backend/error", content=b"client data", headers={"Content-Type": "application/octet-stream"}
    )
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.text == "Backend down"
    assert mock_route.called
    # REMOVED: del app.dependency_overrides[get_policy]


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
