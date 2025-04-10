"""Default implementation for the ResponseBuilder interface."""

from typing import Dict, Optional

from fastapi import Response
from fastapi.responses import JSONResponse, PlainTextResponse
from httpx import Headers  # For type hinting context.response.headers
from luthien_control.control_policy.exceptions import ControlPolicyError
from luthien_control.core.context import TransactionContext
from luthien_control.core.response_builder.interface import ResponseBuilder


class DefaultResponseBuilder(ResponseBuilder):
    """
    Builds a FastAPI response from the TransactionContext based on successful policy execution.

    Priority for determining final values:
    1. context.data["final_status_code" | "final_headers" | "final_content"]
    2. context.response (for status_code, headers)
    3. context.data["raw_backend_response_body"] (for content)

    Headers are filtered to remove hop-by-hop headers.
    Returns a 500 error response ONLY IF building the response itself fails unexpectedly,
    or if essential data (like status code) is missing after policies ran successfully.
    Policy execution errors (like auth failure) should be handled upstream by exception handlers.
    """

    def __init__(self):
        super().__init__()  # Initializes self.logger
        # Headers that should not be forwarded from backend response to client
        # Based on https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers#hop-by-hop_headers
        # Stored as lowercase strings for case-insensitive matching
        self.hop_by_hop_headers = {
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailers",
            "transfer-encoding",
            "upgrade",
            "content-length",  # Exclude even if present, FastAPI recalculates
            "content-encoding",  # Exclude, FastAPI handles compression if needed
        }

    def _convert_to_fastapi_response(self, response: Response, context: TransactionContext) -> Response:
        """Converts an httpx response to a FastAPI response, filtering hop-by-hop headers."""
        try:
            # Get headers, filtering out hop-by-hop ones
            headers = {}
            media_type = None
            for key, value in response.headers.items():
                key_lower = key.lower()
                if key_lower not in self.hop_by_hop_headers:
                    headers[key] = value
                    if key_lower == "content-type":
                        media_type = value

            # Get content, preferring raw_backend_response_body if available
            content = context.data.get("raw_backend_response_body")
            if content is None and hasattr(response, "content"):
                content = response.content
            if content is None:
                content = b""

            return Response(
                content=content,
                status_code=response.status_code,
                headers=headers,
                media_type=media_type,
            )
        except Exception as e:
            self.logger.exception(
                f"[{context.transaction_id}] Failed to FastAPI-ify response: {e}. Falling back to error handling."
            )
            return None

    def build_response(self, context: TransactionContext, exception: Optional[ControlPolicyError] = None) -> Response:
        """Builds the final FastAPI Response assuming successful policy execution."""

        # If we have a context.response, FastAPI-ify it
        if context.response is not None:
            fastapi_response = self._convert_to_fastapi_response(context.response, context)
            if fastapi_response is not None:
                return fastapi_response
            else:
                self.logger.exception(f"[{context.transaction_id}] Failed to FastAPI-ify context.response.")

        if exception is not None:
            self.logger.exception(
                f"[{context.transaction_id}] Failed to construct response from context.response AND "
                f"exception occurred during policy execution: {exception}"
            )
            return JSONResponse(
                content={
                    "detail": (
                        "Internal Server Error: Failed to build response; Exception occurred during policy execution: "
                        f"{exception}"
                    )
                },
                status_code=500,
            )

        self.logger.exception(f"[{context.transaction_id}] . Returning 500.")
        return PlainTextResponse(
            content=f"Internal Server Error: Failed to build response. TXID: {context.transaction_id}",
            status_code=500,
        )
