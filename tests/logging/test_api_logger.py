"""Test the API logger functionality."""
import json
from typing import Dict, Any, List

import pytest

from luthien_control.logging.api_logger import APILogger

@pytest.fixture
def log_entries() -> List[Dict[str, Any]]:
    """Storage for log entries during tests."""
    return []

@pytest.fixture
def logger(log_entries):
    """Create an APILogger that stores entries in memory."""
    return APILogger(log_entries.append)

def test_log_request(logger, log_entries):
    """Test request logging."""
    logger.log_request(
        method="POST",
        url="https://api.example.com/data",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer secret-token"
        },
        body=json.dumps({"name": "test"}).encode(),
        query_params={"version": "1.0"}
    )
    
    assert len(log_entries) == 1
    log = log_entries[0]
    
    assert log["type"] == "request"
    assert log["method"] == "POST"
    assert log["url"] == "https://api.example.com/data"
    assert log["headers"]["Authorization"] == "[REDACTED]"
    assert log["body"] == {"name": "test"}
    assert log["query_params"] == {"version": "1.0"}
    assert "timestamp" in log

def test_log_response(logger, log_entries):
    """Test response logging."""
    logger.log_response(
        status_code=200,
        headers={"Content-Type": "application/json"},
        body=json.dumps({"id": 123, "status": "success"}).encode()
    )
    
    assert len(log_entries) == 1
    log = log_entries[0]
    
    assert log["type"] == "response"
    assert log["status_code"] == 200
    assert log["body"] == {"id": 123, "status": "success"}
    assert "timestamp" in log

def test_non_json_body(logger, log_entries):
    """Test handling of non-JSON body data."""
    logger.log_request(
        method="POST",
        url="https://api.example.com/text",
        headers={"Content-Type": "text/plain"},
        body="Hello, world!"
    )
    
    assert len(log_entries) == 1
    log = log_entries[0]
    assert log["body"] == "Hello, world!"

def test_invalid_json_body(logger, log_entries):
    """Test handling of invalid JSON data."""
    logger.log_request(
        method="POST",
        url="https://api.example.com/data",
        headers={"Content-Type": "application/json"},
        body="{invalid json}"
    )
    
    assert len(log_entries) == 1
    log = log_entries[0]
    assert log["body"] == "{invalid json}"  # Should return raw string when JSON parsing fails

def test_different_byte_encodings(logger, log_entries):
    """Test handling of different byte encodings."""
    # UTF-16 encoded data
    test_data = {"test": "データ"}
    utf16_data = json.dumps(test_data).encode('utf-16')
    logger.log_request(
        method="POST",
        url="https://api.example.com/data",
        headers={"Content-Type": "application/json"},
        body=utf16_data
    )
    
    assert len(log_entries) == 1
    log = log_entries[0]
    assert log["body"] == test_data  # Should successfully parse JSON regardless of encoding

def test_undecodable_binary(logger, log_entries):
    """Test handling of binary data that can't be decoded with any encoding."""
    # Create a single byte that is invalid in all supported encodings
    binary_data = bytes([0xFF])
    logger.log_request(
        method="POST",
        url="https://api.example.com/binary",
        headers={"Content-Type": "application/octet-stream"},
        body=binary_data
    )
    
    assert len(log_entries) == 1
    log = log_entries[0]
    assert isinstance(log["body"], str)
    # When all decodings fail, it should fall back to str(bytes)
    assert log["body"] == str(binary_data)

def test_empty_inputs(logger, log_entries):
    """Test handling of empty inputs."""
    # Request with no body or query params
    logger.log_request(
        method="GET",
        url="https://api.example.com/data",
        headers={}
    )
    
    assert len(log_entries) == 1
    log = log_entries[0]
    assert "body" not in log
    assert "query_params" not in log
    
    # Response with no body
    logger.log_response(
        status_code=204,
        headers={},
    )
    
    assert len(log_entries) == 2
    log = log_entries[1]
    assert "body" not in log

def test_header_redaction(logger, log_entries):
    """Test header redaction with different cases and variations."""
    headers = {
        "API-KEY": "secret1",
        "Cookie": "session=123",
        "authorization": "Bearer token",
        "Content-Type": "application/json",
        "COOKIE": "other=456",
        "Api-Key": "secret2"
    }
    
    logger.log_request(
        method="GET",
        url="https://api.example.com/data",
        headers=headers
    )
    
    assert len(log_entries) == 1
    log = log_entries[0]
    headers = log["headers"]
    
    # Check sensitive headers are redacted regardless of case
    assert headers["API-KEY"] == "[REDACTED]"
    assert headers["Cookie"] == "[REDACTED]"
    assert headers["authorization"] == "[REDACTED]"
    assert headers["COOKIE"] == "[REDACTED]"
    assert headers["Api-Key"] == "[REDACTED]"
    
    # Non-sensitive headers should remain unchanged
    assert headers["Content-Type"] == "application/json"

if __name__ == "__main__":
    pytest.main([__file__]) 