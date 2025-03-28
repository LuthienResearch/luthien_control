"""Test the policy manager."""
import pytest
from fastapi import Request
import httpx
from luthien_control.policies.manager import PolicyManager
from luthien_control.policies.base import ControlPolicy

class TestPolicy(ControlPolicy):
    """A test policy that modifies requests and responses in a predictable way."""
    
    def __init__(self, name: str):
        self.name = name
    
    async def process_request(self, request, target_url, headers, body):
        # Add a header to track policy execution
        headers = dict(headers)
        headers[f"X-Processed-By-{self.name}"] = "true"
        return {
            'target_url': target_url,
            'headers': headers,
            'body': body
        }
    
    async def process_response(self, request, response, content):
        # Create a new response with our header
        return {
            'status_code': response.status_code,
            'headers': {
                **dict(response.headers),
                f"X-Processed-By-{self.name}": "true"
            },
            'content': content
        }

@pytest.fixture
def mock_request():
    """Create a mock FastAPI request."""
    return Request({"type": "http", "method": "GET", "headers": [], "path": "/"})

@pytest.fixture
def mock_response():
    """Create a mock httpx response."""
    return httpx.Response(200, headers={"Content-Type": "application/json"}, content=b'{"status": "ok"}')

def test_policy_registration():
    """Test policy registration and unregistration."""
    manager = PolicyManager()
    policy = TestPolicy("test1")
    
    # Test registration
    assert len(manager._policies) == 0
    manager.register_policy(policy)
    assert len(manager._policies) == 1
    assert manager._policies[0] == policy
    
    # Test duplicate registration
    manager.register_policy(policy)
    assert len(manager._policies) == 2  # Should allow duplicates
    
    # Test unregistration
    manager.unregister_policy(policy)
    assert len(manager._policies) == 1
    manager.unregister_policy(policy)
    assert len(manager._policies) == 0
    
    # Test unregistering non-existent policy
    manager.unregister_policy(policy)  # Should not raise
    assert len(manager._policies) == 0

@pytest.mark.asyncio
async def test_apply_request_policies(mock_request):
    """Test applying multiple request policies in sequence."""
    manager = PolicyManager()
    policy1 = TestPolicy("policy1")
    policy2 = TestPolicy("policy2")
    manager.register_policy(policy1)
    manager.register_policy(policy2)
    
    test_url = "https://api.example.com/test"
    test_headers = {"Content-Type": "application/json"}
    test_body = b'{"test": true}'
    
    result = await manager.apply_request_policies(
        request=mock_request,
        target_url=test_url,
        headers=test_headers,
        body=test_body
    )
    
    # Verify both policies were applied in sequence
    assert result["target_url"] == test_url
    assert result["body"] == test_body
    assert result["headers"]["X-Processed-By-policy1"] == "true"
    assert result["headers"]["X-Processed-By-policy2"] == "true"
    assert result["headers"]["Content-Type"] == "application/json"

@pytest.mark.asyncio
async def test_apply_response_policies(mock_request, mock_response):
    """Test applying multiple response policies in sequence."""
    manager = PolicyManager()
    policy1 = TestPolicy("policy1")
    policy2 = TestPolicy("policy2")
    manager.register_policy(policy1)
    manager.register_policy(policy2)
    
    test_content = b'{"status": "ok"}'
    
    result = await manager.apply_response_policies(
        request=mock_request,
        response=mock_response,
        content=test_content
    )
    
    # Verify both policies were applied in sequence
    assert result["status_code"] == 200
    assert result["content"] == test_content
    assert result["headers"]["X-Processed-By-policy1"] == "true"
    assert result["headers"]["X-Processed-By-policy2"] == "true"
    assert result["headers"]["content-type"] == "application/json"  # HTTP headers are case-insensitive

@pytest.mark.asyncio
async def test_empty_policy_list(mock_request, mock_response):
    """Test behavior with no registered policies."""
    manager = PolicyManager()
    
    # Test request processing
    test_url = "https://api.example.com/test"
    test_headers = {"Content-Type": "application/json"}
    test_body = b'{"test": true}'
    
    request_result = await manager.apply_request_policies(
        request=mock_request,
        target_url=test_url,
        headers=test_headers,
        body=test_body
    )
    
    assert request_result["target_url"] == test_url
    assert request_result["headers"] == test_headers
    assert request_result["body"] == test_body
    
    # Test response processing
    test_content = b'{"status": "ok"}'
    
    response_result = await manager.apply_response_policies(
        request=mock_request,
        response=mock_response,
        content=test_content
    )
    
    assert response_result["status_code"] == 200
    assert response_result["content"] == test_content
    assert response_result["headers"] == dict(mock_response.headers) 