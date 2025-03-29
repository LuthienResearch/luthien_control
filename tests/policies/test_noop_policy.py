"""Test the noop policy."""
import pytest
from fastapi import Request
import httpx
from luthien_control.policies.examples.noop_policy import NoopPolicy

@pytest.fixture
def mock_request():
    """Create a mock FastAPI request."""
    return Request({"type": "http", "method": "GET", "headers": [], "path": "/"})

@pytest.fixture
def mock_response():
    """Create a mock httpx response."""
    return httpx.Response(200, headers={"Content-Type": "application/json"}, content=b'{"status": "ok"}')

@pytest.mark.asyncio
async def test_process_request(mock_request):
    """Test that process_request returns unmodified request data."""
    policy = NoopPolicy()
    
    test_url = "https://api.example.com/test"
    test_headers = {"Content-Type": "application/json", "Authorization": "Bearer token123"}
    test_body = b'{"test": true}'
    
    result = await policy.process_request(
        request=mock_request,
        target_url=test_url,
        headers=test_headers,
        body=test_body
    )
    
    # Verify nothing was modified
    assert result["target_url"] == test_url
    assert result["headers"] == test_headers
    assert result["body"] == test_body
    # Explicitly check all keys
    assert list(result.keys()) == ['target_url', 'headers', 'body']

@pytest.mark.asyncio
async def test_process_response(mock_request, mock_response):
    """Test that process_response returns unmodified response data."""
    policy = NoopPolicy()
    
    test_content = b'{"status": "ok"}'
    
    result = await policy.process_response(
        request=mock_request,
        response=mock_response,
        content=test_content
    )
    
    # Verify nothing was modified
    assert result["status_code"] == mock_response.status_code
    assert result["headers"] == dict(mock_response.headers)
    assert result["content"] == test_content
    # Explicitly check all keys
    assert list(result.keys()) == ['status_code', 'headers', 'content']

@pytest.mark.asyncio
async def test_process_request_with_none_body(mock_request):
    """Test that process_request handles None body correctly."""
    policy = NoopPolicy()
    
    test_url = "https://api.example.com/test"
    test_headers = {"Content-Type": "application/json"}
    test_body = None
    
    result = await policy.process_request(
        request=mock_request,
        target_url=test_url,
        headers=test_headers,
        body=test_body
    )
    
    # Verify nothing was modified and None body is preserved
    assert result["target_url"] == test_url
    assert result["headers"] == test_headers
    assert result["body"] is None

@pytest.mark.asyncio
async def test_process_response_with_empty_content(mock_request):
    """Test that process_response handles empty content correctly."""
    policy = NoopPolicy()
    
    # Create response with empty content
    empty_response = httpx.Response(204, headers={"Content-Length": "0"})
    test_content = b''
    
    result = await policy.process_response(
        request=mock_request,
        response=empty_response,
        content=test_content
    )
    
    # Verify nothing was modified and empty content is preserved
    assert result["status_code"] == empty_response.status_code
    assert result["headers"] == dict(empty_response.headers)
    assert result["content"] == test_content 