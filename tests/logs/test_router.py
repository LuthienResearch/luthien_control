from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from luthien_control.core.dependencies import get_db_session
from luthien_control.db.exceptions import LuthienDBOperationError, LuthienDBQueryError
from luthien_control.db.sqlmodel_models import LuthienLog
from luthien_control.logs.router import router
from sqlalchemy.ext.asyncio import AsyncSession

# Mark all tests as async
pytestmark = pytest.mark.asyncio

# Create test app with just the logs router
logs_test_app = FastAPI()
logs_test_app.include_router(router)


# Mock database session dependency
async def mock_get_db_session():
    return AsyncMock(spec=AsyncSession)


logs_test_app.dependency_overrides[get_db_session] = mock_get_db_session

client = TestClient(logs_test_app)


async def test_logs_ui_endpoint():
    """Test the logs UI endpoint serves HTML."""
    with patch("luthien_control.logs.router.templates") as mock_templates:
        mock_templates.TemplateResponse.return_value = "HTML content"

        response = client.get("/admin/logs")
        assert response.status_code == 200
        mock_templates.TemplateResponse.assert_called_once()


@patch("luthien_control.logs.router.list_logs")
@patch("luthien_control.logs.router.count_logs")
async def test_get_logs_success(mock_count_logs, mock_list_logs):
    """Test successful retrieval of logs."""
    # Mock data
    mock_log = LuthienLog(
        id=1,
        transaction_id="tx-123",
        datetime=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        datatype="test_type",
        data={"message": "test"},
        notes={"note": "test note"},
    )

    mock_list_logs.return_value = [mock_log]
    mock_count_logs.return_value = 1

    response = client.get("/admin/logs-api/logs")
    assert response.status_code == 200

    data = response.json()
    assert "logs" in data
    assert "pagination" in data
    assert "filters" in data

    assert len(data["logs"]) == 1
    assert data["logs"][0]["id"] == 1
    assert data["logs"][0]["transaction_id"] == "tx-123"
    assert data["logs"][0]["datatype"] == "test_type"

    assert data["pagination"]["total"] == 1
    assert data["pagination"]["limit"] == 100
    assert data["pagination"]["offset"] == 0


@patch("luthien_control.logs.router.list_logs")
@patch("luthien_control.logs.router.count_logs")
async def test_get_logs_with_filters(mock_count_logs, mock_list_logs):
    """Test logs endpoint with various filters."""
    mock_list_logs.return_value = []
    mock_count_logs.return_value = 0

    response = client.get(
        "/admin/logs-api/logs",
        params={
            "transaction_id": "tx-123",
            "datatype": "test_type",
            "limit": 50,
            "offset": 10,
            "start_datetime": "2023-01-01T00:00:00Z",
            "end_datetime": "2023-01-02T00:00:00Z",
        },
    )

    assert response.status_code == 200

    # Verify the mocked functions were called with correct parameters
    mock_list_logs.assert_called_once()
    call_args = mock_list_logs.call_args
    assert call_args.kwargs["transaction_id"] == "tx-123"
    assert call_args.kwargs["datatype"] == "test_type"
    assert call_args.kwargs["limit"] == 50
    assert call_args.kwargs["offset"] == 10


async def test_get_logs_invalid_datetime():
    """Test logs endpoint with invalid datetime format."""
    response = client.get("/admin/logs-api/logs", params={"start_datetime": "invalid-date"})

    assert response.status_code == 400
    assert "Invalid start_datetime format" in response.json()["detail"]


@patch("luthien_control.logs.router.list_logs")
async def test_get_logs_database_error(mock_list_logs):
    """Test logs endpoint handling database errors."""
    mock_list_logs.side_effect = LuthienDBQueryError("Database error")

    response = client.get("/admin/logs-api/logs")
    assert response.status_code == 500
    assert "Failed to retrieve logs from database" in response.json()["detail"]


@patch("luthien_control.logs.router.get_log_by_id")
async def test_get_log_by_id_success(mock_get_log_by_id):
    """Test successful retrieval of a specific log."""
    mock_log = LuthienLog(
        id=1,
        transaction_id="tx-123",
        datetime=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        datatype="test_type",
        data={"message": "test"},
        notes={"note": "test note"},
    )

    mock_get_log_by_id.return_value = mock_log

    response = client.get("/admin/logs-api/logs/1")
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == 1
    assert data["transaction_id"] == "tx-123"
    assert data["datatype"] == "test_type"
    assert data["data"]["message"] == "test"
    assert data["notes"]["note"] == "test note"


@patch("luthien_control.logs.router.get_log_by_id")
async def test_get_log_by_id_not_found(mock_get_log_by_id):
    """Test log not found scenario."""
    mock_get_log_by_id.side_effect = LuthienDBQueryError("Log with ID 999 not found")

    response = client.get("/admin/logs-api/logs/999")
    assert response.status_code == 404
    assert "Log with ID 999 not found" in response.json()["detail"]


@patch("luthien_control.logs.router.get_log_by_id")
async def test_get_log_by_id_database_error(mock_get_log_by_id):
    """Test log endpoint handling database errors."""
    mock_get_log_by_id.side_effect = LuthienDBOperationError("Database error")

    response = client.get("/admin/logs-api/logs/1")
    assert response.status_code == 500
    assert "Failed to retrieve log from database" in response.json()["detail"]


@patch("luthien_control.logs.router.get_unique_datatypes")
async def test_get_datatypes_success(mock_get_unique_datatypes):
    """Test successful retrieval of unique datatypes."""
    mock_get_unique_datatypes.return_value = ["type_a", "type_b", "type_c"]

    response = client.get("/admin/logs-api/metadata/datatypes")
    assert response.status_code == 200

    data = response.json()
    assert data == ["type_a", "type_b", "type_c"]


@patch("luthien_control.logs.router.get_unique_datatypes")
async def test_get_datatypes_database_error(mock_get_unique_datatypes):
    """Test datatypes endpoint handling database errors."""
    mock_get_unique_datatypes.side_effect = LuthienDBQueryError("Database error")

    response = client.get("/admin/logs-api/metadata/datatypes")
    assert response.status_code == 500
    assert "Failed to retrieve datatypes from database" in response.json()["detail"]


@patch("luthien_control.logs.router.get_unique_transaction_ids")
async def test_get_transaction_ids_success(mock_get_unique_transaction_ids):
    """Test successful retrieval of unique transaction IDs."""
    mock_get_unique_transaction_ids.return_value = ["tx-1", "tx-2", "tx-3"]

    response = client.get("/admin/logs-api/metadata/transaction-ids")
    assert response.status_code == 200

    data = response.json()
    assert data == ["tx-1", "tx-2", "tx-3"]


@patch("luthien_control.logs.router.get_unique_transaction_ids")
async def test_get_transaction_ids_with_limit(mock_get_unique_transaction_ids):
    """Test transaction IDs endpoint with limit parameter."""
    mock_get_unique_transaction_ids.return_value = ["tx-1", "tx-2"]

    response = client.get("/admin/logs-api/metadata/transaction-ids", params={"limit": 2})
    assert response.status_code == 200

    # Verify the limit was passed to the function
    mock_get_unique_transaction_ids.assert_called_once()
    call_args = mock_get_unique_transaction_ids.call_args
    assert call_args.kwargs["limit"] == 2


@patch("luthien_control.logs.router.get_unique_transaction_ids")
async def test_get_transaction_ids_database_error(mock_get_unique_transaction_ids):
    """Test transaction IDs endpoint handling database errors."""
    mock_get_unique_transaction_ids.side_effect = LuthienDBOperationError("Database error")

    response = client.get("/admin/logs-api/metadata/transaction-ids")
    assert response.status_code == 500
    assert "Failed to retrieve transaction IDs from database" in response.json()["detail"]


@patch("luthien_control.logs.router.list_logs")
@patch("luthien_control.logs.router.count_logs")
async def test_get_logs_with_html_content(mock_count_logs, mock_list_logs):
    """Test that logs containing HTML are returned as-is in the API response.

    This test documents that the API does not escape HTML content - that's the
    responsibility of the frontend to render it safely as text, not HTML.
    """
    # Mock log with potentially dangerous HTML content
    mock_log = LuthienLog(
        id=1,
        transaction_id="tx-123",
        datetime=datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        datatype="test_type",
        data={
            "message": "<script>alert('XSS')</script>",
            "html_content": "<img src=x onerror=alert('XSS')>",
            "nested": {"value": "<div onclick='malicious()'>Click me</div>"},
        },
        notes={"note": "<b>Bold text</b> and <script>alert('note XSS')</script>"},
    )

    mock_list_logs.return_value = [mock_log]
    mock_count_logs.return_value = 1

    response = client.get("/admin/logs-api/logs")
    assert response.status_code == 200

    data = response.json()

    # Verify the API returns HTML content unescaped
    log_data = data["logs"][0]["data"]
    assert log_data["message"] == "<script>alert('XSS')</script>"
    assert log_data["html_content"] == "<img src=x onerror=alert('XSS')>"
    assert log_data["nested"]["value"] == "<div onclick='malicious()'>Click me</div>"

    # Verify notes also contain unescaped HTML
    assert data["logs"][0]["notes"]["note"] == "<b>Bold text</b> and <script>alert('note XSS')</script>"

    # This behavior is correct - the API should return data as-is.
    # The frontend JavaScript must use textContent or proper escaping when displaying.
