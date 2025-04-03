import json
from typing import Any, Dict, Union

from fastapi import Request, Response
from httpx import Response as HttpxResponse

from luthien_control.policies.base import Policy


class AllCapsPolicy(Policy):
    """A policy that converts the content of chat completion responses to uppercase."""

    async def apply_request_policy(
        self, request: Request, original_body: bytes, request_id: str
    ) -> Union[Dict[str, Any], Response]:
        # Pass request through unmodified
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
        # Default pass-through dictionary
        response_dict = {
            "status_code": backend_response.status_code,
            "headers": dict(backend_response.headers),
            "content": original_response_body,
        }

        # Check if it's a successful chat completion response with JSON content
        content_type = backend_response.headers.get("content-type", "").lower()
        is_json = "application/json" in content_type
        is_success = 200 <= backend_response.status_code < 300

        if is_success and is_json:
            try:
                data = json.loads(original_response_body.decode())
                # Ensure it looks like a chat completion response
                if data.get("object") == "chat.completion" and "choices" in data:
                    modified = False
                    for choice in data.get("choices", []):
                        message = choice.get("message", {})
                        if message.get("role") == "assistant" and "content" in message:
                            if isinstance(message["content"], str):
                                message["content"] = message["content"].upper()
                                modified = True

                    if modified:
                        # Update the content in the dictionary if modified
                        response_dict["content"] = json.dumps(data).encode()
                        # Potentially update Content-Length header if needed (handled by server usually)

            except json.JSONDecodeError:
                # If body isn't valid JSON, just pass through original
                pass
            except Exception:
                 # Handle other potential errors gracefully, pass through original
                pass

        return response_dict
