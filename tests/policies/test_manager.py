"""Unit tests for the PolicyManager."""
import pytest
from unittest.mock import Mock, AsyncMock
from fastapi import Request
import httpx
from luthien_control.policies.manager import PolicyManager
from luthien_control.policies.base import ControlPolicy

@pytest.fixture
def mock_request():
    """Create a mock FastAPI request."""
    return Mock(spec=Request)

@pytest.fixture
def mock_response():
    """Create a mock httpx response."""
    return Mock(spec=httpx.Response, status_code=200, headers={})

@pytest.fixture
def manager():
    """Create a PolicyManager instance."""
    return PolicyManager()

class MockPolicy(ControlPolicy):
    """Mock policy for testing."""
    def __init__(self, name: str):
        self.name = name
        self.request_mock = AsyncMock(return_value=None)
        self.response_mock = AsyncMock(return_value=None)

    async def process_request(self, request, target_url, headers, body):
        # Let the mock handle the return value setup
        result = await self.request_mock(request, target_url, headers, body)
        # Ensure the expected dict structure is returned if mock returns None
        return result if result is not None else {'target_url': target_url, 'headers': headers, 'body': body}

    async def process_response(self, request, response, content):
        # Let the mock handle the return value setup
        result = await self.response_mock(request, response, content)
        # Ensure the expected dict structure is returned if mock returns None
        return result if result is not None else {'status_code': response.status_code, 'headers': dict(response.headers), 'content': content}


def test_register_policy(manager):
    """Test registering a policy."""
    policy = MockPolicy("test_policy")
    manager.register_policy(policy)
    # Policies are stored in the private _policies list
    assert policy in manager._policies

def test_unregister_policy(manager):
    """Test unregistering a policy."""
    policy1 = MockPolicy("policy1")
    policy2 = MockPolicy("policy2")
    manager.register_policy(policy1)
    manager.register_policy(policy2)
    assert policy1 in manager._policies
    assert policy2 in manager._policies

    manager.unregister_policy(policy1)

    assert policy1 not in manager._policies
    assert policy2 in manager._policies # Ensure only the specified policy was removed

def test_unregister_policy_not_registered(manager):
    """Test unregistering a policy that is not registered."""
    policy1 = MockPolicy("policy1")
    policy_not_registered = MockPolicy("not_registered")
    manager.register_policy(policy1)
    initial_policies = list(manager._policies) # Copy the list

    # Should not raise an error
    manager.unregister_policy(policy_not_registered)

    # Ensure the list remains unchanged
    assert manager._policies == initial_policies

@pytest.mark.asyncio
async def test_apply_request_policies_empty(manager, mock_request):
    """Test applying request policies when none are registered."""
    initial_data = {'target_url': "url", 'headers': {"h1": "v1"}, 'body': b'body'}
    result = await manager.apply_request_policies(mock_request, **initial_data)
    assert result == initial_data

@pytest.mark.asyncio
async def test_apply_response_policies_empty(manager, mock_request, mock_response):
    """Test applying response policies when none are registered."""
    initial_content = b'content'
    initial_headers = dict(mock_response.headers)
    result = await manager.apply_response_policies(mock_request, mock_response, initial_content)
    assert result == {'status_code': 200, 'headers': initial_headers, 'content': initial_content}

@pytest.mark.asyncio
async def test_apply_request_policies_single(manager, mock_request):
    """Test applying a single request policy."""
    policy = MockPolicy("policy1")
    manager.register_policy(policy)
    
    initial_data = {'target_url': "url", 'headers': {"h1": "v1"}, 'body': b'body'}
    # Define the policy's intended return value
    policy_return_value = {'target_url': "new_url", 'headers': {"h2": "v2"}, 'body': b'new_body'}
    policy.request_mock.return_value = policy_return_value

    # Calculate expected result BEFORE calling the manager
    expected_data = policy_return_value.copy()
    expected_data['headers'] = {**initial_data['headers'], **policy_return_value['headers']}
    
    # Now call the manager method
    result = await manager.apply_request_policies(mock_request, **initial_data)
    
    # Assert the call to the mock
    policy.request_mock.assert_called_once_with(mock_request, initial_data['target_url'], initial_data['headers'], initial_data['body'])
    
    # Assert the final result
    assert result == expected_data

@pytest.mark.asyncio
async def test_apply_response_policies_single(manager, mock_request, mock_response):
    """Test applying a single response policy."""
    policy = MockPolicy("policy1")
    manager.register_policy(policy)
    
    initial_content = b'content'
    initial_response_headers = dict(mock_response.headers) # Get headers from mock
    # Define the policy's intended return value
    policy_return_value = {'status_code': 201, 'headers': {"h2": "v2"}, 'content': b'new_content'}
    policy.response_mock.return_value = policy_return_value

    # Calculate expected result BEFORE calling the manager
    expected_data = policy_return_value.copy()
    expected_data['headers'] = {**initial_response_headers, **policy_return_value['headers']}
    
    # Now call the manager method
    result = await manager.apply_response_policies(mock_request, mock_response, initial_content)
    
    # Assert the call to the mock
    policy.response_mock.assert_called_once_with(mock_request, mock_response, initial_content)
    
    # Assert the final result
    assert result == expected_data

@pytest.mark.asyncio
async def test_apply_request_policies_multiple(manager, mock_request):
    """Test applying multiple request policies in sequence."""
    policy1 = MockPolicy("policy1")
    policy2 = MockPolicy("policy2")
    manager.register_policy(policy1)
    manager.register_policy(policy2)

    initial_data = {'target_url': "url0", 'headers': {"h0": "v0"}, 'body': b'body0'}
    # Define the return values for each policy
    p1_return_value = {'target_url': "url1", 'headers': {"h1": "v1"}, 'body': b'body1'}
    p2_return_value = {'target_url': "url2", 'headers': {"h2": "v2"}, 'body': b'body2'}

    policy1.request_mock.return_value = p1_return_value
    policy2.request_mock.return_value = p2_return_value

    # Calculate expected headers and final result BEFORE calling manager
    expected_headers_after_p1 = {**initial_data['headers'], **p1_return_value['headers']}
    expected_data = p2_return_value.copy() # Start with p2 result
    expected_headers_final = {**expected_headers_after_p1, **p2_return_value['headers']}
    expected_data['headers'] = expected_headers_final

    # Now call the manager
    result = await manager.apply_request_policies(mock_request, **initial_data)

    # Assert calls to mocks
    policy1.request_mock.assert_called_once_with(mock_request, initial_data['target_url'], initial_data['headers'], initial_data['body'])
    policy2.request_mock.assert_called_once_with(mock_request, p1_return_value['target_url'], expected_headers_after_p1, p1_return_value['body'])

    # Assert final result
    assert result == expected_data

@pytest.mark.asyncio
async def test_apply_response_policies_multiple(manager, mock_request, mock_response):
    """Test applying multiple response policies in sequence."""
    policy1 = MockPolicy("policy1")
    policy2 = MockPolicy("policy2")
    manager.register_policy(policy1)
    manager.register_policy(policy2)

    initial_content = b'content0'
    initial_response_data = {'status_code': mock_response.status_code, 'headers': dict(mock_response.headers), 'content': initial_content}
    # Define return values for policies
    p1_return_value = {'status_code': 201, 'headers': {"h1": "v1"}, 'content': b'content1'}
    p2_return_value = {'status_code': 202, 'headers': {"h2": "v2"}, 'content': b'content2'}

    policy1.response_mock.return_value = p1_return_value
    policy2.response_mock.return_value = p2_return_value

    # Calculate expected final result BEFORE calling manager
    expected_headers_after_p1 = {**initial_response_data['headers'], **p1_return_value['headers']}
    expected_data = p2_return_value.copy()
    expected_headers_final = {**expected_headers_after_p1, **p2_return_value['headers']}
    expected_data['headers'] = expected_headers_final

    # Now call the manager
    result = await manager.apply_response_policies(mock_request, mock_response, initial_content)

    # Assert calls to mocks
    policy1.response_mock.assert_called_once_with(mock_request, mock_response, initial_content)
    # We don't easily check args for policy2 due to response object mutation

    # Assert final result
    assert result == expected_data 