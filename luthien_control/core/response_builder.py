import logging
from typing import Optional

from fastapi import Response
from fastapi.responses import JSONResponse, PlainTextResponse

from luthien_control.control_policy.exceptions import ControlPolicyError
from luthien_control.core.transaction_context import TransactionContext


class ResponseBuilder:
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
        self.logger = logging.getLogger(__name__)
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

    def build_response(self, context: TransactionContext, exception: Optional[ControlPolicyError] = None) -> Response:
        """Builds the final FastAPI Response."""
        final_response: Optional[Response] = None

        # If an explicit policy error was passed in, handle it first
        if exception is not None:
            self.logger.warning(f"[{context.transaction_id}] Building response for explicit policy error: {exception}")
            # Customize error response based on exception type if needed
            return JSONResponse(
                content={"detail": f"Policy Error: {exception}", "transaction_id": str(context.transaction_id)},
                status_code=getattr(exception, "status_code", 500),  # Use status_code from exception if available
            )

        # Determine the source response object to use
        source_response = context.response  # Prefer context.response if set directly by a policy
        if source_response is None:
            source_response = context.data.get("backend_response")  # Fallback to backend response data

        # If we have a source response (either context.response or backend_response)
        if source_response is not None:
            try:
                # Attempt conversion using the determined source response
                final_response = self._convert_to_fastapi_response(source_response, context)
            except Exception as convert_exc:
                # Log the specific conversion error
                self.logger.exception(f"[{context.transaction_id}] Failed during response conversion: {convert_exc}")
                # Fall through to generic error response below

        # If we still don't have a response (context.response was None or conversion failed)
        if final_response is None:
            # Log that we are falling back to a generic error
            self.logger.error(
                f"[{context.transaction_id}] Could not build normal response "
                f"(context.response was {'None' if context.response is None else 'present but conversion failed'}). "
                f"Returning generic error."
            )
            return PlainTextResponse(
                content=f"Internal Server Error: Failed to construct final response. TXID: {context.transaction_id}",
                status_code=500,
            )

        # If conversion succeeded
        return final_response
