"""Control Policy for preparing backend headers."""

import logging
from typing import List, Tuple
from urllib.parse import urlparse

from httpx import Headers  # Import Headers for type hinting and manipulation
from luthien_control.config.settings import Settings
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.core.context import TransactionContext


class PrepareBackendHeadersPolicy(ControlPolicy):
    """
    Prepares headers for the backend request based on the incoming request,
    policy modifications, and proxy configuration.

    Specifically, it:
    - Copies allowed headers from the incoming request (context.request.headers).
    - Excludes hop-by-hop headers.
    - Sets the correct Host header based on the configured BACKEND_URL.
    - Forces Accept-Encoding to 'identity' to avoid potential client decoding issues.

    Assumes context.request exists and has headers populated by a previous policy
    (e.g., InitializeContextPolicy).
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        # Store hop-by-hop headers as lowercase bytes for efficient comparison
        self.hop_by_hop_headers = {
            b"host",
            b"content-length",
            b"transfer-encoding",
            b"connection",
            b"keep-alive",
            b"proxy-authenticate",
            b"proxy-authorization",
            b"te",
            b"trailers",
            b"upgrade",
        }

    async def apply(self, context: TransactionContext) -> TransactionContext:
        """Modifies context.request.headers for backend request."""
        if context.request is None:
            raise ValueError(f"[{context.transaction_id}] Cannot prepare headers: context.request is None")

        self.logger.debug(f"[{context.transaction_id}] Preparing backend headers.")

        backend_headers_list: List[Tuple[bytes, bytes]] = []
        original_headers = context.request.headers  # httpx Headers object

        # Iterate through raw headers (list of tuples of bytes)
        for key_bytes, value_bytes in original_headers.raw:
            if key_bytes.lower() not in self.hop_by_hop_headers:
                backend_headers_list.append((key_bytes, value_bytes))

        # Get backend hostname from settings
        try:
            backend_url_str = self.settings.get_backend_url()
            parsed_backend_url = urlparse(backend_url_str)
            backend_host = parsed_backend_url.hostname
            if not backend_host:
                raise ValueError("Could not parse hostname from BACKEND_URL")

            # Add the correct Host header
            self.logger.info(f"[{context.transaction_id}] PrepareBackend: Adding Host header: {backend_host}")
            backend_headers_list.append((b"host", backend_host.encode("latin-1")))

            # Add x-request-id based on transaction_id
            request_id_str = str(context.transaction_id)
            self.logger.info(f"[{context.transaction_id}] PrepareBackend: Adding X-Request-ID header: {request_id_str}")
            backend_headers_list.append((b"x-request-id", request_id_str.encode("latin-1")))

            # Force Accept-Encoding to identity
            # Remove any existing Accept-Encoding headers first
            backend_headers_list = [(k, v) for k, v in backend_headers_list if k.lower() != b"accept-encoding"]
            self.logger.debug(f"[{context.transaction_id}] Setting Accept-Encoding header to: identity")
            backend_headers_list.append((b"accept-encoding", b"identity"))

        except ValueError as e:
            msg = f"Invalid backend_url configuration: {e}"
            self.logger.error(f"[{context.transaction_id}] {msg}")
            # Re-raise the original error for specific testing, but add context
            raise ValueError(msg) from e

        # Update the request headers in the context
        # Note: This replaces the Headers object on the request
        context.request.headers = Headers(backend_headers_list)

        self.logger.debug(f"[{context.transaction_id}] Backend headers prepared.")
        return context
