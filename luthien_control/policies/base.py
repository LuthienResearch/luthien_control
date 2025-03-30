from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union

from fastapi import Request, Response
from httpx import Response as HttpxResponse # Alias to avoid confusion


class Policy(ABC):
    """Abstract base class for all policies."""

    @abstractmethod
    async def apply_request_policy(
        self, request: Request, original_body: bytes, request_id: str
    ) -> Union[Dict[str, Any], Response]:
        """
        Apply policy logic to an incoming client request.

        Args:
            request: The FastAPI request object.
            original_body: The raw body of the incoming request.
            request_id: A unique identifier for the request.

        Returns:
            - A dictionary containing the potentially modified request data
              (e.g., 'url', 'headers', 'content') to be forwarded to the backend.
            - OR a FastAPI Response object to immediately return to the client,
              bypassing the backend entirely.
        """
        pass

    @abstractmethod
    async def apply_response_policy(
        self,
        backend_response: HttpxResponse,
        original_response_body: bytes,
        request_id: str,
    ) -> Union[Dict[str, Any], Response]:
        """
        Apply policy logic to a response received from the backend.

        Args:
            backend_response: The httpx Response object from the backend.
            original_response_body: The raw body of the backend response.
            request_id: A unique identifier for the request.

        Returns:
            - A dictionary containing the potentially modified response data
              (e.g., 'status_code', 'headers', 'content') to be forwarded
              to the client.
            - OR a FastAPI Response object to construct and send to the client.
              (Use carefully, might bypass standard response construction).
        """
        pass

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()" 