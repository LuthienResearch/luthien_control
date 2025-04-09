"""Default implementation for the ResponseBuilder interface."""

import logging
from typing import Any, Dict, Optional

from fastapi import Response
from fastapi.responses import PlainTextResponse
from httpx import Headers  # For type hinting context.response.headers

from luthien_control.core.context import TransactionContext
from luthien_control.core.response_builder.interface import ResponseBuilder


class DefaultResponseBuilder(ResponseBuilder):
    """
    Builds a FastAPI response from the TransactionContext.

    Priority for determining final values:
    1. context.data["final_status_code" | "final_headers" | "final_content"]
    2. context.response (for status_code, headers)
    3. context.data["raw_backend_response_body"] (for content)

    Headers are filtered to remove hop-by-hop headers before creating the final response.
    Returns a 500 error response if context.response is None and no final values
    are set in context.data.
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
        }

    def build_response(self, context: TransactionContext) -> Response:
        """Builds the final FastAPI Response."""

        final_status: int = 500  # Default
        final_headers_dict: Dict[str, str] = {}
        final_content: bytes = b""
        media_type: Optional[str] = None

        # Determine final values based on priority
        if "final_status_code" in context.data:
            final_status = context.data["final_status_code"]
        elif context.response is not None:
            final_status = context.response.status_code
        # else: defaults to 500

        if "final_headers" in context.data:
            # Assume final_headers is a dict-like structure
            raw_headers = context.data["final_headers"]
        elif context.response is not None:
            raw_headers = context.response.headers  # httpx.Headers object
        else:
            raw_headers = {}  # No headers available

        if "final_content" in context.data:
            final_content = context.data["final_content"]
            # TODO: Handle non-bytes final_content? For now, assume bytes.
            if not isinstance(final_content, bytes):
                self.logger.warning(
                    f"[{context.transaction_id}] 'final_content' in context.data is not bytes ({type(final_content)}). Attempting to encode."
                )
                try:
                    final_content = str(final_content).encode("utf-8")
                except Exception as e:
                    self.logger.error(
                        f"[{context.transaction_id}] Failed to encode 'final_content': {e}. Using empty body."
                    )
                    final_content = b""
        elif "raw_backend_response_body" in context.data:
            final_content = context.data["raw_backend_response_body"]
        elif context.response is not None and hasattr(context.response, "content") and context.response.content:
            # Fallback to response.content if raw body wasn't stored/available
            # This might happen if aread() wasn't called or failed
            self.logger.warning(f"[{context.transaction_id}] Using context.response.content as fallback body.")
            final_content = context.response.content
        # else: defaults to b""

        # Filter headers
        if isinstance(raw_headers, Headers):  # Handle httpx Headers object
            items_to_filter = raw_headers.items()
        elif isinstance(raw_headers, dict):  # Handle dict
            items_to_filter = raw_headers.items()
        else:
            self.logger.warning(
                f"[{context.transaction_id}] Unexpected header type {type(raw_headers)}. Skipping header processing."
            )
            items_to_filter = []

        for key, value in items_to_filter:
            key_lower = key.lower()
            if key_lower not in self.hop_by_hop_headers:
                final_headers_dict[key] = value
                if key_lower == "content-type":
                    media_type = value  # Extract media type for FastAPI Response
            else:
                self.logger.debug(f"[{context.transaction_id}] Filtering hop-by-hop header: {key}")

        # Handle case where no response could be determined
        if context.response is None and "final_status_code" not in context.data:
            self.logger.error(
                f"[{context.transaction_id}] No backend response or final_status_code found in context. Returning 500."
            )
            return PlainTextResponse(
                content="Internal Server Error: No response generated or status determined.", status_code=500
            )

        # Construct the final FastAPI Response
        self.logger.info(
            f"[{context.transaction_id}] Building final response: Status={final_status}, Headers={list(final_headers_dict.keys())}, BodyLength={len(final_content)}"
        )
        return Response(
            content=final_content,
            status_code=final_status,
            headers=final_headers_dict,
            media_type=media_type,
        )
