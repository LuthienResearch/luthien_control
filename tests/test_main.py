from fastapi.testclient import TestClient


def test_read_root(client: TestClient):
    """Test the root endpoint '/'."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Luthien Control Proxy is running."}


def test_health_check(client: TestClient):
    """Test the health check endpoint '/health'."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# TODO: Add more comprehensive tests for the lifespan function
#       - Mock dependencies (Settings, httpx.AsyncClient, db_engine, DependencyContainer)
#       - Verify resource creation, storage in app.state, and cleanup
#       - Test error handling during startup (e.g., DB connection failure)

# TODO: Add tests for OpenAPI generation
#       - Verify create_custom_openapi is called
#       - Potentially check specific parts of the generated schema
