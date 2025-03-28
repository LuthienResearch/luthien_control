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

if __name__ == "__main__":
    test_log_request()
    test_log_response()
    test_non_json_body() 