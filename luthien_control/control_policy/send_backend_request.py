"""Core control policy implementations."""

import logging

import httpx
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.core.context import TransactionContext

logger = logging.getLogger(__name__)


class SendBackendRequestPolicy(ControlPolicy):
    """
    Policy responsible for sending the request to the backend, storing the response,
    and reading the raw response body.
    """

    def __init__(self, http_client: httpx.AsyncClient):
        self.http_client = http_client

    async def apply(self, context: TransactionContext) -> TransactionContext:
        """
        Sends the request in context.request to the backend via http_client.
        Stores the httpx.Response in context.response.
        Reads the raw response body and stores it in context.data["raw_backend_response_body"].
        Handles potential httpx exceptions.
        """
        if not context.request:
            raise ValueError(f"[{context.transaction_id}] Cannot send request: context.request is None")

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

            # --- Build new Request for Backend ---
            original_request = context.request
            backend_request = httpx.Request(
                method=original_request.method,
                url=target_url,
                headers=original_request.headers,
                params=original_request.url.params,
                content=original_request.content,
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

        # Store the response object and the raw body in the context
        context.response = response
        context.data["raw_backend_response_body"] = raw_body

        return context
