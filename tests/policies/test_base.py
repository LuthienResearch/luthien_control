import pytest
from fastapi import Request
import httpx
from luthien_control.policies.base import ControlPolicy

def test_control_policy_interface():
    """Test that ControlPolicy enforces its interface."""
    with pytest.raises(TypeError):
        # Should fail because ControlPolicy is abstract
        ControlPolicy()

def test_control_policy_required_methods():
    """Test that derived classes must implement required methods."""
    # Test missing both methods
    class NoMethods(ControlPolicy):
        pass

    with pytest.raises(TypeError):
        NoMethods()

    # Test missing process_response
    class NoResponse(ControlPolicy):
        async def process_request(self, request, target_url, headers, body):
            return {'target_url': target_url, 'headers': headers, 'body': body}

    with pytest.raises(TypeError):
        NoResponse()

    # Test missing process_request
    class NoRequest(ControlPolicy):
        async def process_response(self, request, response, content):
            return {'status_code': response.status_code, 'headers': dict(response.headers), 'content': content}

    with pytest.raises(TypeError):
        NoRequest()

def test_control_policy_minimal_implementation():
    """Test a minimal valid policy implementation."""
    class MinimalPolicy(ControlPolicy):
        async def process_request(self, request, target_url, headers, body):
            return {'target_url': target_url, 'headers': headers, 'body': body}

        async def process_response(self, request, response, content):
            return {'status_code': response.status_code, 'headers': dict(response.headers), 'content': content}

    # Should not raise any exceptions
    policy = MinimalPolicy()
    assert isinstance(policy, ControlPolicy) 