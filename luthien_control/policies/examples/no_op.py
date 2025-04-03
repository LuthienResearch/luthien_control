from typing import Any, Dict, Union

from fastapi import Request, Response
from httpx import Response as HttpxResponse

from luthien_control.policies.base import Policy


class NoOpPolicy(Policy):
    """A policy that does nothing, simply passes data through."""

    async def apply_request_policy(
        self, request: Request, original_body: bytes, request_id: str
    ) -> Union[Dict[str, Any], Response]:
        # Return the original request data unmodified for forwarding
        return {
            "url": str(request.url),
            "headers": dict(request.headers),
            "content": original_body,
            "method": request.method,
        }

    async def apply_response_policy(
        self,
        backend_response: HttpxResponse,
        original_response_body: bytes,
        request_id: str,
    ) -> Union[Dict[str, Any], Response]:
        # Return the original response data unmodified for forwarding
        return {
            "status_code": backend_response.status_code,
            "headers": dict(backend_response.headers),
            "content": original_response_body,
        }
