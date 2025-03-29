"""Test the APILogger data formatting functionality."""
import json
from datetime import datetime
from unittest.mock import Mock, patch, ANY

import pytest

from luthien_control.logging.api_logger import APILogger

@pytest.fixture
def mock_log_handler():
    """Fixture for a mocked log handler callable."""
    return Mock()

@pytest.fixture
def api_logger(mock_log_handler):
    """Fixture for an APILogger instance with the mocked handler."""
    return APILogger(log_handler=mock_log_handler)

# --- Test log_request --- 

def test_log_request_basic(api_logger, mock_log_handler):
    """Test basic request logging."""
    api_logger.log_request(
        method="GET",
        url="http://test.com/path",
        headers={"Accept": "*/*"}
    )
    mock_log_handler.assert_called_once_with({
        "type": "request",
        "method": "GET",
        "url": "http://test.com/path",
        "headers": {"Accept": "*/*"},
        "timestamp": ANY # Check timestamp exists and format later if needed
    })
    # Check timestamp format
    call_args, _ = mock_log_handler.call_args
    assert isinstance(datetime.fromisoformat(call_args[0]["timestamp"]), datetime)

def test_log_request_with_json_body(api_logger, mock_log_handler):
    """Test request logging with a JSON body."""
    body_dict = {"key": "value", "num": 1}
    body_bytes = json.dumps(body_dict).encode('utf-8')
    api_logger.log_request(
        method="POST",
        url="http://test.com/data",
        headers={"Content-Type": "application/json"},
        body=body_bytes
    )
    mock_log_handler.assert_called_once_with({
        "type": "request",
        "method": "POST",
        "url": "http://test.com/data",
        "headers": {"Content-Type": "application/json"},
        "body": body_dict,
        "timestamp": ANY
    })

def test_log_request_with_text_body(api_logger, mock_log_handler):
    """Test request logging with a non-JSON text body."""
    body_text = "Simple text body"
    api_logger.log_request(
        method="PUT",
        url="http://test.com/text",
        headers={"Content-Type": "text/plain"},
        body=body_text.encode('utf-8') # Pass as bytes
    )
    mock_log_handler.assert_called_once_with({
        "type": "request",
        "method": "PUT",
        "url": "http://test.com/text",
        "headers": {"Content-Type": "text/plain"},
        "body": body_text, # Should be decoded string
        "timestamp": ANY
    })

def test_log_request_with_invalid_json_body(api_logger, mock_log_handler):
    """Test request logging with an invalid JSON body."""
    body_invalid = b'{ "key": "value" '
    api_logger.log_request(
        method="POST",
        url="http://test.com/invalid",
        headers={"Content-Type": "application/json"},
        body=body_invalid
    )
    mock_log_handler.assert_called_once_with({
        "type": "request",
        "method": "POST",
        "url": "http://test.com/invalid",
        "headers": {"Content-Type": "application/json"},
        "body": body_invalid.decode('utf-8'), # Should return original decoded string on parse failure
        "timestamp": ANY
    })

def test_log_request_with_undecodable_body(api_logger, mock_log_handler):
    """Test request logging with undecodable bytes."""
    # bytes([0xFF, 0xFE]) is the UTF-16 LE BOM. It decodes to "" with utf-16.
    # The _parse_json function tries utf-16, gets "", tries json.loads(""), fails, returns "".
    body_undecodable = bytes([0xFF, 0xFE]) 
    api_logger.log_request(
        method="POST",
        url="http://test.com/binary",
        headers={"Content-Type": "application/octet-stream"},
        body=body_undecodable
    )
    mock_log_handler.assert_called_once_with({
        "type": "request",
        "method": "POST",
        "url": "http://test.com/binary",
        "headers": {"Content-Type": "application/octet-stream"},
        "body": '', # Expect empty string now, as it's decodable via utf-16
        "timestamp": ANY
    })

def test_log_request_with_completely_undecodable_body(api_logger, mock_log_handler):
    """Test request logging with bytes undecodable by any attempted encoding."""
    # \x80 is invalid in UTF-8, UTF-16 (needs pair), UTF-32 (needs more bytes), ASCII
    body_undecodable = b'\x80'
    api_logger.log_request(
        method="POST",
        url="http://test.com/invalid",
        headers={"Content-Type": "application/octet-stream"},
        body=body_undecodable
    )
    mock_log_handler.assert_called_once_with({
        "type": "request",
        "method": "POST",
        "url": "http://test.com/invalid",
        "headers": {"Content-Type": "application/octet-stream"},
        "body": str(body_undecodable), # Expect str(bytes) when all decodings fail
        "timestamp": ANY
    })

def test_log_request_with_query_params(api_logger, mock_log_handler):
    """Test request logging with query parameters."""
    query = {"search": "test", "limit": 10}
    api_logger.log_request(
        method="GET",
        url="http://test.com/search",
        headers={"Accept": "*/*"},
        query_params=query
    )
    mock_log_handler.assert_called_once_with({
        "type": "request",
        "method": "GET",
        "url": "http://test.com/search",
        "headers": {"Accept": "*/*"},
        "query_params": query,
        "timestamp": ANY
    })

def test_log_request_header_redaction(api_logger, mock_log_handler):
    """Test that sensitive headers are redacted."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer secret",
        "Cookie": "session=123",
        "API-KEY": "key123",
        "X-Custom": "value"
    }
    api_logger.log_request(
        method="GET",
        url="http://test.com/secure",
        headers=headers
    )
    mock_log_handler.assert_called_once_with({
        "type": "request",
        "method": "GET",
        "url": "http://test.com/secure",
        "headers": {
            "Content-Type": "application/json",
            "Authorization": "[REDACTED]",
            "Cookie": "[REDACTED]",
            "API-KEY": "[REDACTED]",
            "X-Custom": "value"
        },
        "timestamp": ANY
    })

# --- Test log_response --- 

def test_log_response_basic(api_logger, mock_log_handler):
    """Test basic response logging."""
    api_logger.log_response(
        status_code=204,
        headers={"Server": "TestServer"}
    )
    mock_log_handler.assert_called_once_with({
        "type": "response",
        "status_code": 204,
        "headers": {"Server": "TestServer"},
        "timestamp": ANY
    })
    # Check timestamp format
    call_args, _ = mock_log_handler.call_args
    assert isinstance(datetime.fromisoformat(call_args[0]["timestamp"]), datetime)

def test_log_response_with_json_body(api_logger, mock_log_handler):
    """Test response logging with a JSON body."""
    body_dict = {"status": "ok", "id": 123}
    body_bytes = json.dumps(body_dict).encode('utf-8')
    api_logger.log_response(
        status_code=200,
        headers={"Content-Type": "application/json"},
        body=body_bytes
    )
    mock_log_handler.assert_called_once_with({
        "type": "response",
        "status_code": 200,
        "headers": {"Content-Type": "application/json"},
        "body": body_dict,
        "timestamp": ANY
    })

def test_log_response_with_text_body(api_logger, mock_log_handler):
    """Test response logging with a non-JSON text body."""
    body_text = "Success"
    api_logger.log_response(
        status_code=200,
        headers={"Content-Type": "text/plain"},
        body=body_text.encode('utf-8')
    )
    mock_log_handler.assert_called_once_with({
        "type": "response",
        "status_code": 200,
        "headers": {"Content-Type": "text/plain"},
        "body": body_text,
        "timestamp": ANY
    })

def test_log_response_header_redaction(api_logger, mock_log_handler):
    """Test sensitive headers are redacted in responses (though less common)."""
    headers = {
        "Content-Type": "application/json",
        "Set-Cookie": "session=456; HttpOnly", # Example sensitive header
        "X-Request-ID": "abc"
    }
    api_logger.log_response(
        status_code=200,
        headers=headers,
        body=b'{"data": "test"}'
    )
    mock_log_handler.assert_called_once_with({
        "type": "response",
        "status_code": 200,
        "headers": {
            "Content-Type": "application/json",
            "Set-Cookie": "[REDACTED]", # Check if Set-Cookie is redacted (it should be)
            "X-Request-ID": "abc"
        },
        "body": {"data": "test"},
        "timestamp": ANY
    })

if __name__ == "__main__":
    pytest.main([__file__]) 