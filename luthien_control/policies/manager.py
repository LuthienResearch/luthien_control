"""
Manager for control policies in the Luthien Control Framework.
"""
from typing import Dict, List, Any, Optional
from fastapi import Request
import httpx

from .base import ControlPolicy

class PolicyManager:
    """
    Manages the registration and execution of control policies.
    """
    
    def __init__(self):
        """Initialize an empty list of policies."""
        self._policies: List[ControlPolicy] = []
    
    def register_policy(self, policy: ControlPolicy) -> None:
        """
        Register a new control policy.
        
        Args:
            policy: The policy to register
        """
        self._policies.append(policy)
    
    def unregister_policy(self, policy: ControlPolicy) -> None:
        """
        Unregister a control policy.
        
        Args:
            policy: The policy to unregister
        """
        if policy in self._policies:
            self._policies.remove(policy)
    
    async def apply_request_policies(self, request: Request, target_url: str, 
                                    headers: Dict[str, str], body: Optional[bytes]) -> Dict[str, Any]:
        """
        Apply all request policies in sequence.
        
        Args:
            request: The original FastAPI request
            target_url: The URL where the request will be sent
            headers: The headers that will be sent
            body: The request body as bytes
            
        Returns:
            Dict containing potentially modified request components
        """
        request_data = {
            'target_url': target_url,
            'headers': headers,
            'body': body
        }
        
        for policy in self._policies:
            policy_result = await policy.process_request(
                request, 
                request_data['target_url'], 
                request_data['headers'], 
                request_data['body']
            )
            request_data.update(policy_result)
        
        return request_data
    
    async def apply_response_policies(self, request: Request, response: httpx.Response, 
                                     content: bytes) -> Dict[str, Any]:
        """
        Apply all response policies in sequence.
        
        Args:
            request: The original FastAPI request
            response: The response from the target API
            content: The response content as bytes
            
        Returns:
            Dict containing potentially modified response components
        """
        response_data = {
            'status_code': response.status_code,
            'headers': dict(response.headers),
            'content': content
        }
        
        for policy in self._policies:
            policy_result = await policy.process_response(request, response, response_data['content'])
            response_data.update(policy_result)
        
        return response_data 