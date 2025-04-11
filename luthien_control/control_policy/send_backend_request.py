"""Core control policy implementations."""

import logging
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import Request  # Added for type hint
from luthien_control.config.settings import Settings
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.core.context import TransactionContext

logger = logging.getLogger(__name__)


class SendBackendRequestPolicy(ControlPolicy):
    """
    Policy responsible for sending the request to the backend, storing the response,
    and reading the raw response body.
    Reads settings from context.settings.
    """

    _EXCLUDED_BACKEND_HEADERS = {
        b"host",
        b"content-length",
        b"transfer-encoding",
        b"accept-encoding",  # We force identity
        b"authorization",  # We add our own
    }

    def __init__(self, http_client: httpx.AsyncClient):
        self.http_client = http_client

    def _build_target_url(self, context: TransactionContext, base_url: str, relative_path: str) -> str:
        """Constructs the full target URL for the backend request."""
        # Ensure no double slashes
        target_url = f"{base_url.rstrip('/')}/{relative_path.lstrip('/')}"
        logger.debug(
            f"[{context.transaction_id}] Constructed target URL: {target_url} "
            f"(from base: {base_url}, relative: {relative_path})"
        )
        return target_url

    def _prepare_backend_headers(
        self, context: TransactionContext, original_request: Request, settings: Settings
    ) -> list[tuple[bytes, bytes]]:
        """Prepares the headers to be sent to the backend."""
        backend_headers: list[tuple[bytes, bytes]] = []
        backend_url_base = settings.get_backend_url()  # Already validated in apply

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
        openai_key = settings.get_openai_api_key()
        if not openai_key:
            logger.error(f"[{context.transaction_id}] OPENAI_API_KEY not found in settings.")
            raise ValueError("Backend API key (OPENAI_API_KEY) not configured.")
        backend_headers.append((b"authorization", f"Bearer {openai_key}".encode("latin-1")))

        logger.debug(f"[{context.transaction_id}] Prepared backend headers: {len(backend_headers)} headers")
        # Consider logging the actual headers only at TRACE level if sensitive
        return backend_headers

    async def apply(self, context: TransactionContext) -> TransactionContext:
        """
        Sends the request in context.request to the backend via http_client.
        Stores the httpx.Response in context.data["backend_response"].
        Reads the raw response body and stores it in context.data["raw_backend_response_body"].
        Handles potential httpx exceptions.
        Requires context.settings to be set.
        """
        # --- Pre-flight Checks ---
        if not context.request:
            raise ValueError(f"[{context.transaction_id}] Cannot send request: context.request is None")
        if not hasattr(context, "settings") or not isinstance(context.settings, Settings):
            raise ValueError(
                f"[{context.transaction_id}] Cannot send request: context.settings not available or invalid type."
            )

        relative_path = context.data.get("relative_path")
        if not relative_path:
            raise ValueError(f"[{context.transaction_id}] Cannot send request: relative_path not found in context.data")

        backend_url_base = context.settings.get_backend_url()
        if not backend_url_base:
            raise ValueError(f"[{context.transaction_id}] Cannot send request: BACKEND_URL not configured in settings")
        # OPENAI_API_KEY is checked within _prepare_backend_headers

        # --- Prepare Request Components ---
        try:
            target_url = self._build_target_url(context, backend_url_base, relative_path)
            backend_headers = self._prepare_backend_headers(context, context.request, context.settings)
        except ValueError as e:
            # Configuration or header preparation error
            logger.error(
                f"[{context.transaction_id}] Error preparing backend request components: {e}",
                extra={"request_id": context.transaction_id},
            )
            raise  # Re-raise the configuration error

        # --- Build and Send Backend Request ---
        backend_request: httpx.Request | None = None
        response: httpx.Response | None = None
        raw_body: bytes | None = None
        try:
            backend_request = httpx.Request(
                method=context.request.method,
                url=target_url,
                headers=backend_headers,
                params=context.request.url.params,
                content=context.request.content,  # Use original raw content
            )

            logger.debug(
                f"[{context.transaction_id}] Sending request to backend: {backend_request.method} {backend_request.url}"
            )
            response = await self.http_client.send(backend_request)
            logger.debug(f"[{context.transaction_id}] Received backend response: {response.status_code}")

            # Read the raw body immediately
            raw_body = await response.aread()
            logger.debug(f"[{context.transaction_id}] Read {len(raw_body)} bytes from backend response body.")

        except (httpx.TimeoutException, httpx.RequestError) as e:
            request_url_for_log = backend_request.url if backend_request else target_url  # Fallback
            error_type = type(e).__name__
            logger.error(
                f"[{context.transaction_id}] {error_type} connecting to backend '{request_url_for_log}': {e}",
                extra={"request_id": context.transaction_id},
            )
            context.response = None  # Clear any partial response state
            context.data.pop("backend_response", None)
            context.data.pop("raw_backend_response_body", None)
            raise  # Re-raise the httpx error
        except Exception as e:
            request_url_for_log = backend_request.url if backend_request else target_url
            logger.exception(
                f"[{context.transaction_id}] Unexpected error during backend request "
                f"to '{request_url_for_log}' or body read: {e}",
                extra={"request_id": context.transaction_id},
            )
            context.response = None  # Clear any partial response state
            context.data.pop("backend_response", None)
            context.data.pop("raw_backend_response_body", None)
            raise  # Re-raise the unexpected error

        # --- Store Results ---
        # Explicitly set context.response to None as per original logic,
        # the actual response is handled via context.data
        context.response = None
        context.data["backend_response"] = response  # Store the httpx response object here
        context.data["raw_backend_response_body"] = raw_body

        return context

    def serialize_config(self) -> dict[str, Any]:
        """Serializes config. Returns base info as only dependency is http_client."""
        # Ensure http_client is not accidentally serialized
        return {
            "__policy_type__": self.__class__.__name__,
            "name": self.name,
            "policy_class_path": self.policy_class_path,
            # Do not include http_client here
        }
