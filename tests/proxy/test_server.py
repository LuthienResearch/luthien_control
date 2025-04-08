# tests/proxy/test_server.py
import json  # Add json import
from typing import Any, Dict

import httpx
import pytest
import respx
from fastapi import FastAPI, Request, Response, status
from fastapi.testclient import TestClient
from luthien_control.dependencies import get_policy  # To override
from luthien_control.main import app  # Import your main FastAPI app
from luthien_control.policies.base import Policy

# --- Mock Policy Implementations ---


class MockNoOpPolicy(Policy):
    """Mimics NoOpPolicy for testing default behavior."""

    async def apply_request_policy(self, request: Request, original_body: bytes, request_id: str) -> Dict[str, Any]:
        return {"content": original_body, "headers": request.headers.raw}

    async def apply_response_policy(
        self, backend_response: httpx.Response, original_response_body: bytes, request_id: str
    ) -> Dict[str, Any]:
        return {
            "content": original_response_body,
            "headers": backend_response.headers,
            "status_code": backend_response.status_code,
        }


class ModifyRequestPolicy(Policy):
    """Adds a header and modifies body in request."""

    async def apply_request_policy(self, request: Request, original_body: bytes, request_id: str) -> Dict[str, Any]:
        headers = list(request.headers.raw)
        headers.append((b"X-Req-Policy", b"Applied"))
        modified_body = original_body + b" [REQ_MODIFIED]"
        return {"content": modified_body, "headers": headers}

    async def apply_response_policy(
        self, backend_response: httpx.Response, original_response_body: bytes, request_id: str
    ) -> Dict[str, Any]:
        # No change on response
        return {
            "content": original_response_body,
            "headers": backend_response.headers,
            "status_code": backend_response.status_code,
        }


class ModifyResponsePolicy(Policy):
    """Changes status code and modifies body in response."""

    async def apply_request_policy(self, request: Request, original_body: bytes, request_id: str) -> Dict[str, Any]:
        # No change on request
        return {"content": original_body, "headers": request.headers.raw}

    async def apply_response_policy(
        self, backend_response: httpx.Response, original_response_body: bytes, request_id: str
    ) -> Dict[str, Any]:
        headers = dict(backend_response.headers)
        headers["X-Resp-Policy"] = "Applied"
        modified_body = original_response_body + b" [RESP_MODIFIED]"
        return {
            "content": modified_body,
            "headers": headers,
            "status_code": status.HTTP_202_ACCEPTED,  # Change status code
        }


class DirectRequestResponsePolicy(Policy):
    """Returns a direct response during request phase."""

    async def apply_request_policy(self, request: Request, original_body: bytes, request_id: str) -> Response:
        return Response(content=b"Direct from Request Policy", status_code=status.HTTP_418_IM_A_TEAPOT)

    async def apply_response_policy(
        self, backend_response: httpx.Response, original_response_body: bytes, request_id: str
    ) -> Dict[str, Any]:
        pass  # Should not be called


class DirectResponseResponsePolicy(Policy):
    """Returns a direct response during response phase."""

    async def apply_request_policy(self, request: Request, original_body: bytes, request_id: str) -> Dict[str, Any]:
        # No change on request
        return {"content": original_body, "headers": request.headers.raw}

    async def apply_response_policy(
        self, backend_response: httpx.Response, original_response_body: bytes, request_id: str
    ) -> Response:
        return Response(content=b"Direct from Response Policy", status_code=status.HTTP_201_CREATED)


class RequestPolicyError(Policy):
    """Raises an error during request policy application."""

    async def apply_request_policy(self, request: Request, original_body: bytes, request_id: str) -> Dict[str, Any]:
        raise ValueError("Request Policy Failed!")

    async def apply_response_policy(
        self, backend_response: httpx.Response, original_response_body: bytes, request_id: str
    ) -> Dict[str, Any]:
        pass  # Should not be called


class ResponsePolicyError(Policy):
    """Raises an error during response policy application."""

    async def apply_request_policy(self, request: Request, original_body: bytes, request_id: str) -> Dict[str, Any]:
        return {"content": original_body, "headers": request.headers.raw}

    async def apply_response_policy(
        self, backend_response: httpx.Response, original_response_body: bytes, request_id: str
    ) -> Dict[str, Any]:
        raise ValueError("Response Policy Failed!")


# --- Pytest Fixtures ---

# Use override_settings for tests needing specific settings
# Example: @pytest.mark.parametrize("override_settings", [{"POLICY_MODULE": ...}])


@pytest.fixture(autouse=True)
def clear_policy_cache():
    """Ensure the policy cache in dependencies is cleared before each test."""
    # Access the private variable to reset it. This is test-specific.
    from luthien_control import dependencies

    dependencies._cached_policy = None
    yield
    dependencies._cached_policy = None  # Clear after test too


@pytest.fixture
def test_app() -> FastAPI:
    """Returns the FastAPI app instance for testing."""
    # Ensure dependency overrides are cleared if applied globally before
    # We handle overrides per-test now.
    app.dependency_overrides = {}
    return app


@pytest.fixture
def client(test_app: FastAPI) -> TestClient:
    """Provides a FastAPI test client that correctly handles lifespan events."""
    # Use the lifespan context manager when creating the client
    with TestClient(test_app) as test_client:
        yield test_client
    # No explicit shutdown needed here, TestClient context manager handles it.


# --- Test Cases ---


@respx.mock
def test_proxy_with_no_op_policy(client: TestClient):
    """Test basic proxying with the default NoOpPolicy (or equivalent mock)."""
    # Get the settings instance injected by the override fixture
    settings = client.app.state.test_settings

    # Ensure NoOpPolicy (or mock equivalent) is loaded
    app.dependency_overrides[get_policy] = lambda: MockNoOpPolicy()

    # Use the BACKEND_URL from the actual test settings for the mock route
    backend_url_str = settings.get_backend_url().rstrip("/")
    backend_route = respx.post(f"{backend_url_str}/test/path").mock(
        return_value=httpx.Response(200, json={"backend": "ok"})
    )

    # Use json parameter for TestClient to handle Content-Type automatically
    client_payload = {"client": "hello"}
    response = client.post("/test/path?q=1", json=client_payload, headers={"X-Client-Header": "Value"})

    assert response.status_code == 200
    assert response.json() == {"backend": "ok"}
    assert backend_route.called

    request_sent = backend_route.calls[0].request
    assert request_sent.headers["x-client-header"] == "Value"
    # Parse the sent content and compare dicts to ignore whitespace differences
    sent_payload = json.loads(request_sent.content)
    assert sent_payload == client_payload

    # Clean up override
    del app.dependency_overrides[get_policy]


@respx.mock
def test_proxy_modify_request_policy(client: TestClient):
    """Test policy modifying the request before forwarding."""
    settings = client.app.state.test_settings
    app.dependency_overrides[get_policy] = lambda: ModifyRequestPolicy()

    backend_url_str = settings.get_backend_url().rstrip("/")
    backend_route = respx.post(f"{backend_url_str}/modify/req").mock(
        return_value=httpx.Response(200, text="Backend got it")
    )

    # Add default Content-Type for raw content
    response = client.post(
        "/modify/req", content=b"original data", headers={"Content-Type": "application/octet-stream"}
    )

    assert response.status_code == 200
    assert response.text == "Backend got it"
    assert backend_route.called
    request_sent = backend_route.calls[0].request
    assert request_sent.headers["x-req-policy"] == "Applied"
    assert request_sent.content == b"original data [REQ_MODIFIED]"

    del app.dependency_overrides[get_policy]


@respx.mock
def test_proxy_modify_response_policy(client: TestClient):
    """Test policy modifying the response from the backend."""
    settings = client.app.state.test_settings
    app.dependency_overrides[get_policy] = lambda: ModifyResponsePolicy()

    backend_url_str = settings.get_backend_url().rstrip("/")
    backend_route = respx.post(f"{backend_url_str}/modify/resp").mock(
        return_value=httpx.Response(200, content=b"backend content")
    )

    # Add default Content-Type for raw content
    response = client.post("/modify/resp", content=b"client data", headers={"Content-Type": "application/octet-stream"})

    assert response.status_code == status.HTTP_202_ACCEPTED
    assert response.content == b"backend content [RESP_MODIFIED]"
    assert response.headers["x-resp-policy"] == "Applied"
    assert backend_route.called

    del app.dependency_overrides[get_policy]


@respx.mock
def test_proxy_direct_request_response_policy(client: TestClient):
    """Test policy returning a direct response during request phase."""
    settings = client.app.state.test_settings
    app.dependency_overrides[get_policy] = lambda: DirectRequestResponsePolicy()

    backend_url_str = settings.get_backend_url().rstrip("/")
    # Backend should NOT be called, but we still need the URL for respx pattern potentially
    backend_route = respx.post(f"{backend_url_str}/direct/req").mock(
        return_value=httpx.Response(200, text="SHOULD NOT BE CALLED")
    )

    # Add default Content-Type for raw content
    response = client.post("/direct/req", content=b"client data", headers={"Content-Type": "application/octet-stream"})

    assert response.status_code == status.HTTP_418_IM_A_TEAPOT
    assert response.content == b"Direct from Request Policy"
    assert not backend_route.called

    del app.dependency_overrides[get_policy]


@respx.mock
def test_proxy_direct_response_response_policy(client: TestClient):
    """Test policy returning a direct response during response phase."""
    settings = client.app.state.test_settings
    app.dependency_overrides[get_policy] = lambda: DirectResponseResponsePolicy()

    backend_url_str = settings.get_backend_url().rstrip("/")
    backend_route = respx.post(f"{backend_url_str}/direct/resp").mock(
        return_value=httpx.Response(200, content=b"backend original")
    )

    # Add default Content-Type for raw content
    response = client.post("/direct/resp", content=b"client data", headers={"Content-Type": "application/octet-stream"})

    assert response.status_code == status.HTTP_201_CREATED
    assert response.content == b"Direct from Response Policy"
    assert backend_route.called

    del app.dependency_overrides[get_policy]


@respx.mock
def test_proxy_request_policy_error(client: TestClient):
    """Test handling of error during request policy execution."""
    settings = client.app.state.test_settings
    app.dependency_overrides[get_policy] = lambda: RequestPolicyError()

    backend_url_str = settings.get_backend_url().rstrip("/")
    backend_route = respx.post(f"{backend_url_str}/err/req").mock(
        return_value=httpx.Response(200, text="SHOULD NOT BE CALLED")
    )

    # Add default Content-Type for raw content
    response = client.post("/err/req", content=b"client data", headers={"Content-Type": "application/octet-stream"})

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    # Check specific error message if needed, FastAPI might wrap it
    # assert "Error applying request policy" in response.text
    # Check the detail field in the JSON response for FastAPI's structured error
    assert response.json()["detail"] == "Error applying request policy."
    assert not backend_route.called

    del app.dependency_overrides[get_policy]


@respx.mock
def test_proxy_response_policy_error(client: TestClient):
    """Test handling of error during response policy execution."""
    settings = client.app.state.test_settings
    app.dependency_overrides[get_policy] = lambda: ResponsePolicyError()

    backend_url_str = settings.get_backend_url().rstrip("/")
    backend_route = respx.post(f"{backend_url_str}/err/resp").mock(
        return_value=httpx.Response(200, content=b"backend ok")
    )

    # Add default Content-Type for raw content
    response = client.post("/err/resp", content=b"client data", headers={"Content-Type": "application/octet-stream"})

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    # assert "Error applying response policy" in response.text
    assert response.json()["detail"] == "Error applying response policy."
    assert backend_route.called

    del app.dependency_overrides[get_policy]


@respx.mock
def test_proxy_backend_error_passthrough(client: TestClient):
    """Test that backend errors are proxied correctly (if policy doesn't interfere)."""
    settings = client.app.state.test_settings
    # Use a simple policy for this test
    app.dependency_overrides[get_policy] = lambda: MockNoOpPolicy()

    backend_url_str = settings.get_backend_url().rstrip("/")
    backend_route = respx.post(f"{backend_url_str}/backend/error").mock(
        return_value=httpx.Response(status.HTTP_503_SERVICE_UNAVAILABLE, text="Backend down")
    )

    # Add default Content-Type for raw content
    response = client.post(
        "/backend/error", content=b"client data", headers={"Content-Type": "application/octet-stream"}
    )

    # Assert that the proxy returns the same status code as the backend error
    # Changed expected status from 502 to 503
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.text == "Backend down" # Verify body passthrough too
    assert backend_route.called

    del app.dependency_overrides[get_policy]
