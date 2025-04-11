"""Core control policy implementations."""

import logging
from typing import Any
from urllib.parse import urlparse

import httpx
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

    def __init__(self, http_client: httpx.AsyncClient):
        self.http_client = http_client

    async def apply(self, context: TransactionContext) -> TransactionContext:
        """
        Sends the request in context.request to the backend via http_client.
        Stores the httpx.Response in context.data["backend_response"].
        Reads the raw response body and stores it in context.data["raw_backend_response_body"].
        Handles potential httpx exceptions.
        Requires context.settings to be set.
        """
        if not context.request:
            raise ValueError(f"[{context.transaction_id}] Cannot send request: context.request is None")
        if not hasattr(context, "settings") or not isinstance(context.settings, Settings):
            raise ValueError(
                f"[{context.transaction_id}] Cannot send request: context.settings not available or invalid type."
            )

        response: httpx.Response | None = None
        raw_body: bytes | None = None
        backend_request: httpx.Request | None = None
        try:
            # --- Construct Backend URL ---
            relative_path = context.data.get("relative_path")
            if not relative_path:
                raise ValueError(
                    f"[{context.transaction_id}] Cannot send request: relative_path not found in context.data"
                )

            backend_url_base = context.settings.get_backend_url()
            if not backend_url_base:
                raise ValueError(
                    f"[{context.transaction_id}] Cannot send request: BACKEND_URL not configured in settings"
                )

            # Ensure no double slashes
            target_url = f"{backend_url_base.rstrip('/')}/{relative_path.lstrip('/')}"
            # --- End Construct Backend URL ---

            logger.debug(f"[{context.transaction_id}] SendBackendPolicy Calculated URL Parts:")
            logger.debug(f"  - backend_url_base: {backend_url_base}")
            logger.debug(f"  - relative_path   : {relative_path}")
            logger.debug(f"  - final target_url: {target_url}")

            # --- Prepare Backend Headers ---
            original_request = context.request
            backend_headers = []
            excluded_headers = {b"host", b"content-length", b"transfer-encoding", b"accept-encoding", b"authorization"}

            # Copy necessary headers from original request, excluding problematic ones
            for key_bytes, value_bytes in original_request.headers.raw:
                if key_bytes.lower() not in excluded_headers:
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
                    f"[{context.transaction_id}] Invalid BACKEND_URL for Host header: {e}",
                    extra={"request_id": context.transaction_id},
                )
                raise ValueError(f"Could not parse scheme or netloc from BACKEND_URL: {e}")

            # Force Accept-Encoding: identity (See issue #1)
            backend_headers.append((b"accept-encoding", b"identity"))

            # --- Add Backend Authorization Header ---
            openai_key = context.settings.get_openai_api_key()
            if not openai_key:
                logger.error(f"[{context.transaction_id}] OPENAI_API_KEY not found in settings.")
                raise ValueError("Backend API key not configured.")
            backend_headers.append((b"authorization", f"Bearer {openai_key}".encode("latin-1")))
            # --- End Backend Authorization Header ---

            # --- Build new Request for Backend ---
            # Use prepared headers
            backend_request = httpx.Request(
                method=original_request.method,
                url=target_url,
                headers=backend_headers,  # Use prepared headers
                params=original_request.url.params,
                content=original_request.content,  # Revert back to using .content
            )
            # --- End Build new Request ---

            logger.debug(
                f"[{context.transaction_id}] Sending request to backend: {backend_request.method} {backend_request.url}"
            )
            response = await self.http_client.send(backend_request)
            logger.debug(f"[{context.transaction_id}] Received backend response: {response.status_code}")

            # Read the raw body immediately
            raw_body = await response.aread()
            logger.debug(f"[{context.transaction_id}] Read {len(raw_body)} bytes from backend response body.")

        except httpx.TimeoutException as e:
            request_url_for_log = backend_request.url if backend_request else "<unknown>"
            logger.error(
                f"[{context.transaction_id}] Timeout connecting to backend '{request_url_for_log}': {e}",
                extra={"request_id": context.transaction_id},
            )
            # Store None and re-raise
            context.response = None
            context.data.pop("raw_backend_response_body", None)
            raise
        except httpx.RequestError as e:
            request_url_for_log = backend_request.url if backend_request else "<unknown>"
            # Includes ConnectError, ReadError, etc.
            logger.error(
                f"[{context.transaction_id}] Error connecting to backend '{request_url_for_log}': {e}",
                extra={"request_id": context.transaction_id},
            )
            context.response = None
            context.data.pop("raw_backend_response_body", None)
            raise
        except Exception as e:
            request_url_for_log = backend_request.url if backend_request else "<unknown>"
            # Catch other potential errors during send or aread
            logger.exception(
                f"[{context.transaction_id}] Unexpected error during backend request or body read: {e}",
                extra={"request_id": context.transaction_id},
            )
            context.response = None
            context.data.pop("raw_backend_response_body", None)
            raise

        # Store the response object in context.data and the raw body
        context.response = None  # Ensure this remains None for normal flow
        context.data["backend_response"] = response  # Store the httpx response object here
        context.data["raw_backend_response_body"] = raw_body

        return context

    def serialize_config(self) -> dict[str, Any]:
        """Serializes config. Returns base info as only dependency is http_client."""
        return {
            "__policy_type__": self.__class__.__name__,
            "name": self.name,
            "policy_class_path": self.policy_class_path,
        }
