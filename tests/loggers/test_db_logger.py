from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Request, Response

# Assuming absolute imports
from luthien_control.logging.db_logger import log_db_entry

# Mark all tests in this module as async tests
pytestmark = pytest.mark.asyncio


# Helper to create mock Request/Response objects
def create_mock_request_response(
    method="POST",
    url_path="/api/v1/chat",
    client_ip="192.168.1.1",
    host="test.example.com",
):
    # Construct the full URL string
    url = f"http://{host}{url_path}"
    mock_request_scope = {
        "type": "http",
        "method": method,
        "scheme": "http",
        "server": (host, 80),
        "path": url_path,
        "headers": [(b"content-type", b"application/json")],  # Example header
        "client": (client_ip, 12345) if client_ip else None,
        "root_path": "",  # Add root_path for url construction
        "query_string": b"",  # Add query_string
    }
    mock_request = Request(mock_request_scope)

    # Mock response headers needs to be available via .headers attribute which behaves like a dict/mapping
    mock_response_headers = {"content-length": "100", "x-api-key": "test-key"}
    mock_response = Response(
        status_code=200, content=b'{"success": true}', headers=mock_response_headers
    )

    return mock_request, mock_response, url  # Return constructed URL for assertion


@patch("luthien_control.logging.db_logger.get_db_pool", new_callable=MagicMock)
@patch("luthien_control.logging.db_logger.log_request_response", new_callable=AsyncMock)
async def test_log_db_entry_passes_correct_data(mock_log_req_resp, mock_get_pool):
    """Test log_db_entry extracts data and calls log_request_response correctly."""
    mock_pool_instance = AsyncMock()
    mock_get_pool.return_value = mock_pool_instance

    # Don't simulate NotImplementedError anymore
    # mock_log_req_resp.side_effect = NotImplementedError("Database logging logic not yet implemented.")

    mock_request, mock_response, expected_url = create_mock_request_response()
    request_body = b'{"input": "data"}'
    response_body = b'{"output": "result"}'

    # Add a placeholder for processing time calculation (likely done in middleware later)
    start_time = 1700000000.0
    end_time = 1700000000.150
    processing_time_ms = int((end_time - start_time) * 1000)

    # Call the function
    # We may need to pass start/end time eventually, or calculate it inside
    await log_db_entry(
        request=mock_request,
        response=mock_response,
        request_body=request_body,
        response_body=response_body,
        # processing_time_ms=processing_time_ms # Pass if added as arg later
    )

    # Verify that get_db_pool was called
    mock_get_pool.assert_called_once()

    # Verify that log_request_response was called with expected arguments
    mock_log_req_resp.assert_awaited_once()
    call_args = mock_log_req_resp.call_args[1]  # Use keyword args for robustness

    assert call_args["pool"] == mock_pool_instance
    assert call_args["client_ip"] == "192.168.1.1"

    # Check extracted request data
    assert call_args["request_data"]["method"] == "POST"
    # Ensure the full URL is captured
    assert call_args["request_data"]["url"] == expected_url
    assert call_args["request_data"]["headers"] == {"content-type": "application/json"}
    assert call_args["request_data"]["body"] == '{"input": "data"}'
    # assert 'processing_time_ms' in call_args['request_data'] # Add when implemented

    # Check extracted response data
    assert call_args["response_data"]["status_code"] == 200
    # Response headers from FastAPI Response are accessed via .headers
    assert call_args["response_data"]["headers"] == {
        "content-length": "100",
        "x-api-key": "test-key",
    }
    assert call_args["response_data"]["body"] == '{"output": "result"}'


# TODO: Add tests for error handling (e.g., pool not initialized, unexpected exceptions)
# TODO: Add tests for handling missing request/response bodies
