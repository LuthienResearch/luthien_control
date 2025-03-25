"""Test the API logger functionality."""
import json
import os
from pathlib import Path
from .api_logger import APILogger, DEFAULT_LOGS_DIR

def test_api_logger():
    """Test API logger with various request/response scenarios."""
    # Test 1: Using default log location
    print("\nTest 1: Using default log location")
    default_logger = APILogger()
    print(f"Logs will be written to: {default_logger.log_file}")
    
    default_logger.log_request(
        method="POST",
        url="https://api.example.com/data",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer secret-token"
        },
        body=json.dumps({"name": "test"}).encode(),
        query_params={"version": "1.0"}
    )
    
    default_logger.log_response(
        status_code=200,
        headers={"Content-Type": "application/json"},
        body=json.dumps({"id": 123, "status": "success"}).encode()
    )
    
    # Test 2: Using custom log location
    print("\nTest 2: Using custom log location")
    custom_log_file = DEFAULT_LOGS_DIR / "custom_test.json"
    custom_logger = APILogger(log_file=str(custom_log_file))
    print(f"Logs will be written to: {custom_logger.log_file}")
    
    custom_logger.log_request(
        method="POST",
        url="https://api.example.com/upload",
        headers={
            "Content-Type": "application/octet-stream",
            "Cookie": "session=abc123"
        },
        body=b'\x00\x01\x02\x03'
    )
    
    custom_logger.log_response(
        status_code=201,
        headers={"Content-Type": "text/plain"},
        body=b"Upload successful"
    )
    
    # Print contents of both log files
    print("\nDefault log file contents:")
    with open(default_logger.log_file, 'r') as f:
        print(f.read())
    
    print("\nCustom log file contents:")
    with open(custom_logger.log_file, 'r') as f:
        print(f.read())
    
    # Clean up test files
    os.remove(default_logger.log_file)
    os.remove(custom_logger.log_file)
    
    # Try to remove the api logs directory if empty
    try:
        DEFAULT_LOGS_DIR.rmdir()
        DEFAULT_LOGS_DIR.parent.rmdir()  # Remove parent 'logs' dir if empty
    except OSError:
        # Directory not empty or already removed, that's fine
        pass

if __name__ == "__main__":
    test_api_logger() 