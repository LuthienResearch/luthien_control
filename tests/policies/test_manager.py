"""Test the policy manager."""
import pytest
from fastapi import Request
import httpx
from luthien_control.policies import PolicyManager, ControlPolicy

class SimpleTestPolicy(ControlPolicy):
    """A simple test policy that modifies request and response."""
    async def process_request(self, request, target_url, headers, body):
        return {
            'target_url': target_url + '/test',
            'headers': headers,
            'body': body
        }
    
    async def process_response(self, request, response, content):
        return {
            'status_code': 200,
            'headers': {'X-Test': 'true'},
            'content': b'test'
        }

@pytest.fixture
def manager():
    """Create a policy manager for testing."""
    return PolicyManager()

@pytest.fixture
def policy():
    """Create a test policy."""
    return SimpleTestPolicy()

def test_register_unregister(manager, policy):
    """Test registering and unregistering policies."""
    assert len(manager._policies) == 0
    manager.register_policy(policy)
    assert len(manager._policies) == 1
    manager.unregister_policy(policy)
    assert len(manager._policies) == 0

@pytest.mark.asyncio
async def test_apply_request_policies(manager, policy):
    """Test applying request policies."""
    manager.register_policy(policy)
    result = await manager.apply_request_policies(
        request=None,
        target_url='http://test.com',
        headers={},
        body=None
    )
    assert result['target_url'] == 'http://test.com/test'

@pytest.mark.asyncio
async def test_apply_response_policies(manager, policy):
    """Test applying response policies."""
    manager.register_policy(policy)
    response = httpx.Response(200, content=b'original')
    result = await manager.apply_response_policies(
        request=None,
        response=response,
        content=b'original'
    )
    assert result['content'] == b'test'
    assert result['headers']['X-Test'] == 'true' 