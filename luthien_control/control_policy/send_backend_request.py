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
        try:
            logger.debug(
                f"[{context.transaction_id}] Sending request to backend: {context.request.method} {context.request.url}"
            )
            response = await self.http_client.send(context.request)
            logger.debug(f"[{context.transaction_id}] Received backend response: {response.status_code}")

            # Read the raw body immediately
            raw_body = await response.aread()
            logger.debug(f"[{context.transaction_id}] Read {len(raw_body)} bytes from backend response body.")

        except httpx.TimeoutException as e:
            logger.error(
                f"[{context.transaction_id}] Timeout connecting to backend '{context.request.url}': {e}",
                extra={"request_id": context.transaction_id},  # Assuming request_id=transaction_id
            )
            # Store None and re-raise
            context.response = None
            context.data.pop("raw_backend_response_body", None)
            raise  # Re-raise the original exception
        except httpx.RequestError as e:
            # Includes ConnectError, ReadError, etc.
            logger.error(
                f"[{context.transaction_id}] Error connecting to backend '{context.request.url}': {e}",
                extra={"request_id": context.transaction_id},
            )
            context.response = None
            context.data.pop("raw_backend_response_body", None)
            raise
        except Exception as e:
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
