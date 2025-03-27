"""
No-operation control policy for the Luthien Control Framework.
"""
from typing import Dict, Any, Optional
from fastapi import Request
import httpx

from ..base import ControlPolicy

class NoopPolicy(ControlPolicy):
    """
    A control policy that performs no operations on requests or responses.
    
    This serves as a default policy and can be used as a base class for other policies
    that only need to override one of the processing methods.
    """
    
    async def process_request(self, request: Request, target_url: str, 
                             headers: Dict[str, str], body: Optional[bytes]) -> Dict[str, Any]:
        """
        Process a request without modifying it.
        
        Args:
            request: The original FastAPI request
            target_url: The URL where the request will be sent
            headers: The headers that will be sent
            body: The request body as bytes
            
        Returns:
            Dict containing unchanged request components
        """
        return {
            'target_url': target_url,
            'headers': headers,
            'body': body
        }
    
    async def process_response(self, request: Request, response: httpx.Response, 
                              content: bytes) -> Dict[str, Any]:
        """
        Process a response without modifying it.
        
        Args:
            request: The original FastAPI request
            response: The response from the target API
            content: The response content as bytes
            
        Returns:
            Dict containing unchanged response components
        """
        return {
            'status_code': response.status_code,
            'headers': dict(response.headers),
            'content': content
        } 