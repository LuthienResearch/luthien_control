import time
import uuid
from typing import Any, Dict, Union

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from httpx import Response as HttpxResponse

from luthien_control.policies.base import Policy


class NahBruhPolicy(Policy):
    """A policy that intercepts chat completion requests and returns a fixed response."""

    async def apply_request_policy(
        self, request: Request, original_body: bytes, request_id: str
    ) -> Union[Dict[str, Any], Response]:
        # Check if it's a chat completion request
        if request.method == "POST" and request.url.path.endswith("chat/completions"):
            # Construct the "nah bruh" response
            response_data = {
                "id": f"chatcmpl-{uuid.uuid4()!s}",
                "object": "chat.completion",
                "created": int(time.time()),
                "model": "nah-bruh-model", # Indicate the policy intercepted
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "nah bruh",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }
            return JSONResponse(content=response_data, status_code=status.HTTP_200_OK)

        # If not a chat completion request, pass through
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
        # This policy only acts on requests, so pass response through
        return {
            "status_code": backend_response.status_code,
            "headers": dict(backend_response.headers),
            "content": original_response_body,
        }
