"""Core control policy implementations."""

import logging
from typing import Optional, cast
from urllib.parse import urlparse

import httpx
from luthien_control.config.settings import Settings
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.transaction_context import TransactionContext

logger = logging.getLogger(__name__)


class SendBackendRequestPolicy(ControlPolicy):
    """
    Policy responsible for sending the request to the backend, storing the response,
    and reading the raw response body.
    """

    REQUIRED_DEPENDENCIES = ["http_client", "settings"]

    _EXCLUDED_BACKEND_HEADERS = {
        b"host",
        b"transfer-encoding",
        b"accept-encoding",  # We force identity
        b"authorization",  # We add our own
    }

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        settings: Settings,
        name: Optional[str] = None,
    ):
        self.name: str = name or self.__class__.__name__
        self.http_client: httpx.AsyncClient = http_client
        self.settings: Settings = settings

    def _build_target_url(self, base_url: str, relative_path: str) -> str:
        """Constructs the full target URL for the backend request."""
        # Ensure no double slashes
        target_url = f"{base_url.rstrip('/')}/{relative_path.lstrip('/')}"
        logger.debug(f"Constructed target URL: {target_url} (from base: {base_url}, relative: {relative_path})")
        return target_url

    def _prepare_backend_headers(self, context: TransactionContext) -> list[tuple[bytes, bytes]]:
        """Prepares the headers to be sent to the backend."""
        original_request = context.request
        backend_headers: list[tuple[bytes, bytes]] = []
        backend_url_base = self.settings.get_backend_url()  # Already validated in apply

        # Copy necessary headers from original request, excluding problematic ones
        for key_bytes, value_bytes in original_request.headers.raw:
            if key_bytes.lower() not in self._EXCLUDED_BACKEND_HEADERS:
                backend_headers.append((key_bytes, value_bytes))

        # Add the correct Host header for the backend
        try:
            parsed_backend_url = urlparse(backend_url_base)
            backend_host = parsed_backend_url.hostname
            if not backend_host:
                raise ValueError("Could not parse hostname from BACKEND_URL")
            backend_headers.append((b"host", backend_host.encode("latin-1")))
        except ValueError as e:
            logger.error(
                f"[{context.transaction_id}] Invalid BACKEND_URL '{backend_url_base}' for Host header parsing: {e}",
                extra={"request_id": context.transaction_id},
            )
            # Raise a more specific internal error if needed, or let apply handle it
            raise ValueError(f"Could not determine backend Host from BACKEND_URL: {e}")

        # Force Accept-Encoding: identity (avoids downstream decompression issues)
        backend_headers.append((b"accept-encoding", b"identity"))

        # Add Backend Authorization Header
        openai_key = self.settings.get_openai_api_key()
        backend_headers.append((b"authorization", f"Bearer {openai_key}".encode("latin-1")))

        return backend_headers

    async def apply(self, context: TransactionContext) -> TransactionContext:
        """
        Sends context.request to the backend and stores the response as context.data["backend_response"]

        Handles potential httpx exceptions.
        """
        # --- Pre-flight Checks ---
        if not context.request:
            raise ValueError(f"[{context.transaction_id}] Cannot send request: context.request is None")

        backend_url_base = self.settings.get_backend_url()

        # --- Prepare Request Components ---
        try:
            target_url = self._build_target_url(backend_url_base, context.request.url.path)
            backend_headers = self._prepare_backend_headers(context)
            # TODO: We should ideally create a *new* request object here
            # rather than mutating the existing one. Mutating might have
            # unintended side effects if the original request object is used
            # elsewhere or if retries happen.
            # For now, keep mutation for simplicity, but flag for future refactor.
            context.request.url = httpx.URL(target_url)  # Ensure it's a URL object
            context.request.headers = httpx.Headers(backend_headers)  # Ensure it's a Headers object
        except ValueError as e:
            # Configuration or header preparation error
            logger.error(
                f"[{context.transaction_id}] Error preparing backend request components: {e}",
                extra={"request_id": context.transaction_id},
            )
            raise  # Re-raise the configuration error

        # --- Send Backend Request ---
        try:
            logger.debug(
                f"[{context.transaction_id}] Sending request to backend: {context.request.method} {context.request.url}"
            )
            # Send the modified context.request directly
            response = await self.http_client.send(context.request)
            # Read response body immediately to ensure connection is closed
            await response.aread()
            context.data["backend_response"] = response
            logger.debug(f"[{context.transaction_id}] Received backend response: {response.status_code}")
            logger.debug(f"[{context.transaction_id}] Read {len(response.content)} bytes from backend response body.")

        except (httpx.TimeoutException, httpx.RequestError) as e:
            request_url_for_log = context.request.url if context.request else target_url  # Fallback
            error_type = type(e).__name__
            logger.error(
                f"[{context.transaction_id}] {error_type} connecting to backend '{request_url_for_log}': {e}",
                extra={"request_id": context.transaction_id},
            )
            raise  # Re-raise the httpx error
        except Exception as e:
            request_url_for_log = context.request.url if context.request else target_url
            logger.exception(
                f"[{context.transaction_id}] Unexpected error during backend request "
                f"to '{request_url_for_log}' or body read: {e}",
                extra={"request_id": context.transaction_id},
            )
            raise  # Re-raise the unexpected error

        return context

    def serialize(self) -> SerializableDict:
        """Serializes config. Returns base info as only dependency is http_client."""
        # Return an empty dictionary literal, cast to SerializableDict for type checker
        return cast(SerializableDict, {"name": self.name})

    @classmethod
    async def from_serialized(
        cls,
        config: SerializableDict,
        http_client: httpx.AsyncClient,
        settings: Settings,
        **kwargs,
    ) -> "SendBackendRequestPolicy":
        return cls(name=config.get("name"), http_client=http_client, settings=settings)
