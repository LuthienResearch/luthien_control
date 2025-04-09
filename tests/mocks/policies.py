from typing import Any, Dict

import httpx
from fastapi import Request, Response, status
from luthien_control.policies.base import Policy


class MockNoOpPolicy(Policy):
    """Mimics NoOpPolicy for testing default behavior."""

    def __init__(self):
        super().__init__()

    async def apply_request_policy(self, request: Request, original_body: bytes, request_id: str) -> Dict[str, Any]:
        return {"content": original_body, "headers": request.headers.raw}

    async def apply_response_policy(
        self, backend_response: httpx.Response, original_response_body: bytes, request_id: str
    ) -> Dict[str, Any]:
        return {
            "content": original_response_body,
            "headers": backend_response.headers,
            "status_code": backend_response.status_code,
        }


class ModifyRequestPolicy(Policy):
    """Adds a header and modifies body in request."""

    async def apply_request_policy(self, request: Request, original_body: bytes, request_id: str) -> Dict[str, Any]:
        headers = list(request.headers.raw)
        headers.append((b"X-Req-Policy", b"Applied"))
        modified_body = original_body + b" [REQ_MODIFIED]"
        return {"content": modified_body, "headers": headers}

    async def apply_response_policy(
        self, backend_response: httpx.Response, original_response_body: bytes, request_id: str
    ) -> Dict[str, Any]:
        # No change on response
        return {
            "content": original_response_body,
            "headers": backend_response.headers,
            "status_code": backend_response.status_code,
        }


class ModifyResponsePolicy(Policy):
    """Changes status code and modifies body in response."""

    async def apply_request_policy(self, request: Request, original_body: bytes, request_id: str) -> Dict[str, Any]:
        # No change on request
        return {"content": original_body, "headers": request.headers.raw}

    async def apply_response_policy(
        self, backend_response: httpx.Response, original_response_body: bytes, request_id: str
    ) -> Dict[str, Any]:
        headers = dict(backend_response.headers)
        headers["X-Resp-Policy"] = "Applied"
        modified_body = original_response_body + b" [RESP_MODIFIED]"
        return {
            "content": modified_body,
            "headers": headers,
            "status_code": status.HTTP_202_ACCEPTED,  # Change status code
        }


class DirectRequestResponsePolicy(Policy):
    """Returns a direct response during request phase."""

    async def apply_request_policy(self, request: Request, original_body: bytes, request_id: str) -> Response:
        return Response(content=b"Direct from Request Policy", status_code=status.HTTP_418_IM_A_TEAPOT)

    async def apply_response_policy(
        self, backend_response: httpx.Response, original_response_body: bytes, request_id: str
    ) -> Dict[str, Any]:
        pass  # Should not be called


class DirectResponseResponsePolicy(Policy):
    """Returns a direct response during response phase."""

    async def apply_request_policy(self, request: Request, original_body: bytes, request_id: str) -> Dict[str, Any]:
        # No change on request
        return {"content": original_body, "headers": request.headers.raw}

    async def apply_response_policy(
        self, backend_response: httpx.Response, original_response_body: bytes, request_id: str
    ) -> Response:
        return Response(content=b"Direct from Response Policy", status_code=status.HTTP_201_CREATED)


class RequestPolicyError(Policy):
    """Raises an error during request policy application."""

    async def apply_request_policy(self, request: Request, original_body: bytes, request_id: str) -> Dict[str, Any]:
        raise ValueError("Request Policy Failed!")

    async def apply_response_policy(
        self, backend_response: httpx.Response, original_response_body: bytes, request_id: str
    ) -> Dict[str, Any]:
        pass  # Should not be called


class ResponsePolicyError(Policy):
    """Raises an error during response policy application."""

    async def apply_request_policy(self, request: Request, original_body: bytes, request_id: str) -> Dict[str, Any]:
        return {"content": original_body, "headers": request.headers.raw}

    async def apply_response_policy(
        self, backend_response: httpx.Response, original_response_body: bytes, request_id: str
    ) -> Dict[str, Any]:
        raise ValueError("Response Policy Failed!")
