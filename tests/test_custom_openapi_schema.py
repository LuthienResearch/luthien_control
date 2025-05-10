from unittest.mock import patch

import pytest
from fastapi import FastAPI
from luthien_control.custom_openapi_schema import create_custom_openapi


@pytest.fixture
def test_app() -> FastAPI:
    """Provides a minimal FastAPI app instance for testing."""
    app = FastAPI(title="Test App", version="1.0")

    @app.get("/proxy/{full_path:path}")
    async def proxy_endpoint(full_path: str):
        return {"path": full_path}

    @app.get("/other/{item_id}")
    async def other_endpoint(item_id: int):
        return {"item": item_id}

    # Clear any cached schema before returning
    app.openapi_schema = None
    return app


# --- Test Cases --- #


def test_create_custom_openapi_sets_allow_reserved(test_app: FastAPI):
    """Verify that allowReserved=True is set for the {full_path} parameter."""
    schema = create_custom_openapi(test_app)

    assert isinstance(schema, dict)
    paths = schema.get("paths", {})
    proxy_path_key = "/proxy/{full_path}"
    assert proxy_path_key in paths

    path_item = paths[proxy_path_key]
    assert "get" in path_item
    method_item = path_item["get"]
    parameters = method_item.get("parameters", [])

    found_param = False
    for param in parameters:
        if param.get("name") == "full_path" and param.get("in") == "path":
            found_param = True
            assert param.get("allowReserved") is True
            break

    assert found_param, "'full_path' path parameter not found or correctly modified."


def test_create_custom_openapi_does_not_modify_other_params(test_app: FastAPI):
    """Verify that other parameters are not inadvertently modified."""
    schema = create_custom_openapi(test_app)

    paths = schema.get("paths", {})
    other_path_key = "/other/{item_id}"
    assert other_path_key in paths

    path_item = paths[other_path_key]
    assert "get" in path_item
    method_item = path_item["get"]
    parameters = method_item.get("parameters", [])

    found_param = False
    for param in parameters:
        if param.get("name") == "item_id" and param.get("in") == "path":
            found_param = True
            # Ensure allowReserved is NOT set or is False for other params
            assert param.get("allowReserved", False) is False
            break

    assert found_param, "'item_id' path parameter not found."


@patch("luthien_control.custom_openapi_schema.get_openapi")
def test_create_custom_openapi_caching(mock_get_openapi: patch, test_app: FastAPI):
    """Verify that the generated schema is cached on the app instance."""
    # Setup mock return value
    mock_schema = {"openapi": "3.1.0", "info": {"title": "Mock Schema"}, "paths": {}}
    mock_get_openapi.return_value = mock_schema

    # First call - should call get_openapi
    schema1 = create_custom_openapi(test_app)
    assert schema1 is mock_schema
    assert test_app.openapi_schema is mock_schema  # Check if cached
    mock_get_openapi.assert_called_once()

    # Reset mock for the second call check
    mock_get_openapi.reset_mock()

    # Second call - should return cached schema, not call get_openapi
    schema2 = create_custom_openapi(test_app)
    assert schema2 is mock_schema  # Should be the same cached object
    mock_get_openapi.assert_not_called()
