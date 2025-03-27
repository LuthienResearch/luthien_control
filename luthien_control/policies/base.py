"""
Base classes for control policies in the Luthien Control Framework.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union
from fastapi import Request, Response
import httpx

class ControlPolicy(ABC):
    """
    Abstract base class for all control policies.
    
    Control policies can modify or inspect requests before they are sent to the target API
    and responses before they are returned to the client.
    """
    
    @abstractmethod
    async def process_request(self, request: Request, target_url: str, 
                             headers: Dict[str, str], body: Optional[bytes]) -> Dict[str, Any]:
        """
        Process a request before it is sent to the target API.
        
        Args:
            request: The original FastAPI request
            target_url: The URL where the request will be sent
            headers: The headers that will be sent
            body: The request body as bytes
            
        Returns:
            Dict containing potentially modified request components:
            {
                'target_url': str,
                'headers': Dict[str, str],
                'body': Optional[bytes]
            }
        """
        pass
    
    @abstractmethod
    async def process_response(self, request: Request, response: httpx.Response, 
                              content: bytes) -> Dict[str, Any]:
        """
        Process a response before it is returned to the client.
        
        Args:
            request: The original FastAPI request
            response: The response from the target API
            content: The response content as bytes
            
        Returns:
            Dict containing potentially modified response components:
            {
                'status_code': int,
                'headers': Dict[str, str],
                'content': bytes
            }
        """
        pass 