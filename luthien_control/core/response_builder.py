import logging

from fastapi import Response
from fastapi.responses import JSONResponse

from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.tracked_context import TrackedContext


class ResponseBuilder:
    """
    Builds a FastAPI response from the TrackedContext based on successful policy execution.

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

    def _convert_to_fastapi_response(self, context: TrackedContext) -> Response:
        """Converts a TrackedResponse to a FastAPI Response object.

        Filters hop-by-hop headers. The content, status code, and headers
        are taken directly from the tracked response.

        Args:
            context: The tracked context with response data.

        Returns:
            A FastAPI Response object.

        Raises:
            TypeError: if response is None or invalid.
        """
        # This check is a safeguard; callers should ideally ensure type correctness.
        if context.response is None:
            self.logger.error(f"[{context.transaction_id}] _convert_to_fastapi_response received None response.")
            raise TypeError("_convert_to_fastapi_response received None response.")

        # Filter headers from the backend response
        filtered_backend_headers = {
            k: v for k, v in context.response.headers.items() if k.lower() not in self.hop_by_hop_headers
        }

        # Extract media type from backend response headers if present
        media_type = context.response.headers.get("content-type")

        # Create a FastAPI Response using details from tracked response
        return Response(
            content=context.response.content,
            status_code=context.response.status_code,
            headers=filtered_backend_headers,
            media_type=media_type,
        )

    def build_response(self, context: TrackedContext, dependencies: DependencyContainer) -> Response:
        try:
            return self._convert_to_fastapi_response(context)
        except Exception as convert_exc:  # Catch any other unexpected error during conversion
            self.logger.exception(
                f"[{context.transaction_id}] Unexpected error during conversion of context.response: {convert_exc}"
            )
            if dependencies.settings.dev_mode():
                return JSONResponse(
                    content={
                        "detail": f"Policy Error: {str(convert_exc)}",
                        "transaction_id": str(context.transaction_id),
                    },
                    status_code=500,
                )
            else:
                return JSONResponse(
                    content={
                        "detail": "Internal Server Error",
                        "transaction_id": str(context.transaction_id),
                    },
                    status_code=500,
                )
