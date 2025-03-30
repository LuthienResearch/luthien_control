import json

import pytest
import respx
from fastapi.testclient import TestClient
from httpx import AsyncClient, RequestError, Response

# Import the Settings type for type hinting if needed, and the fixture
from luthien_control.config.settings import Settings

# Import the app, not the global settings instance
from luthien_control.proxy.server import app

# Mark all tests in this module as unit tests
pytestmark = pytest.mark.unit

# Remove the conditional setting of BACKEND_URL
# if not settings.BACKEND_URL:
#     settings.BACKEND_URL = "http://mock-backend.test"


@pytest.fixture(name="client")
def client_fixture(app):  # Depends on the app fixture now
    """Pytest fixture for the FastAPI TestClient.
    The override_settings_dependency fixture runs automatically (autouse=True).
    """
    with TestClient(app) as test_client:
        yield test_client


# Test functions will go here


# Use respx to mock the httpx client used by the app
@respx.mock
def test_proxy_get_success(client: TestClient, unit_settings: Settings):
    """Test successful GET request proxying."""
    # Use settings from the fixture to build the mock URL
    backend_host = unit_settings.BACKEND_URL.host
    backend_port = unit_settings.BACKEND_URL.port
    backend_url = f"http://{backend_host}:{backend_port}/test/path"
    route = respx.get(backend_url).mock(
        return_value=Response(200, json={"message": "Success"})
    )

    response = client.get("/test/path")

    assert route.called
    assert response.status_code == 200
    assert response.json() == {"message": "Success"}


@respx.mock
def test_proxy_post_success(client: TestClient, unit_settings: Settings):
    """Test successful POST request proxying with body."""
    backend_host = unit_settings.BACKEND_URL.host
    backend_port = unit_settings.BACKEND_URL.port
    backend_url = f"http://{backend_host}:{backend_port}/submit/data"
    route = respx.post(backend_url).mock(
        return_value=Response(201, json={"status": "Created"})
    )

    response = client.post("/submit/data", json={"key": "value"})

    assert route.called
    # Check that the backend received the correct body
    request = route.calls.last.request
    assert json.loads(request.content) == {"key": "value"}
    assert response.status_code == 201
    assert response.json() == {"status": "Created"}


@respx.mock
def test_proxy_forwards_query_params(client: TestClient, unit_settings: Settings):
    """Test that query parameters are correctly forwarded."""
    backend_host = unit_settings.BACKEND_URL.host
    backend_port = unit_settings.BACKEND_URL.port
    backend_url_pattern = f"http://{backend_host}:{backend_port}/search"
    route = respx.get(url__regex=f"^{backend_url_pattern}\\?.*").mock(
        return_value=Response(200, json={"results": []})
    )

    response = client.get("/search?query=test&limit=10")

    assert route.called
    request = route.calls.last.request
    assert request.url.query == b"query=test&limit=10"
    assert response.status_code == 200
    assert response.json() == {"results": []}


@respx.mock
def test_proxy_forwards_headers(client: TestClient, unit_settings: Settings):
    """Test that specific headers are forwarded and backend headers are returned."""
    backend_host = unit_settings.BACKEND_URL.host
    backend_port = unit_settings.BACKEND_URL.port
    backend_url = f"http://{backend_host}:{backend_port}/headers/check"
    mock_response_headers = {
        "X-Backend-Header": "BackendValue",
        "Content-Type": "application/xml",
    }
    route = respx.get(backend_url).mock(
        return_value=Response(200, text="<data/>", headers=mock_response_headers)
    )

    client_headers = {"X-Custom-Header": "ClientValue", "Accept": "application/xml"}
    response = client.get("/headers/check", headers=client_headers)

    assert route.called
    request = route.calls.last.request
    # Note: TestClient/httpx might add/modify standard headers (like host, accept-encoding, connection)
    assert request.headers["x-custom-header"] == "ClientValue"
    assert request.headers["accept"] == "application/xml"

    assert response.status_code == 200
    assert response.text == "<data/>"
    assert response.headers["x-backend-header"] == "BackendValue"
    # Check a standard header modified by the proxy/backend
    assert response.headers["content-type"] == "application/xml"
    # Verify transfer-encoding is handled (often added for streaming)


@respx.mock
def test_proxy_backend_connection_error(client: TestClient, unit_settings: Settings):
    """Test handling of backend connection errors (e.g., timeout, DNS error)."""
    backend_host = unit_settings.BACKEND_URL.host
    backend_port = unit_settings.BACKEND_URL.port
    backend_url = f"http://{backend_host}:{backend_port}/error/path"
    route = respx.get(backend_url).mock(side_effect=RequestError("Connection failed"))

    response = client.get("/error/path")

    assert route.called
    assert response.status_code == 502  # Bad Gateway
    assert "Error connecting to backend: Connection failed" in response.text
