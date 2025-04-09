"""Control Policy for initializing the TransactionContext from a FastAPI Request."""

import logging
from typing import Optional

import httpx
from fastapi import Request

from luthien_control.config.settings import Settings  # Keep for potential future use, or policy config
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.core.context import TransactionContext


class InitializeContextPolicy(ControlPolicy):
    """
    Initializes the context.request from the incoming FastAPI request.

    Reads the request body and prepares the initial httpx.Request object
    using the method, headers, query parameters, and body from the incoming request.
    The target URL is initially set based on the incoming request path and query parameters,
    acting as a placeholder until potentially modified by downstream policies.
    Stores the original raw body in context.data["raw_request_body"].
    """

    def __init__(self, settings: Optional[Settings] = None):  # Settings might not be needed now
        # self.settings = settings # Store if needed for policy config
        self.logger = logging.getLogger(__name__)

    async def apply(self, context: TransactionContext, fastapi_request: Optional[Request] = None) -> TransactionContext:
        """
        Initializes context.request from fastapi_request.

        Requires fastapi_request to be passed explicitly.
        Raises ValueError if fastapi_request is None.
        """
        if fastapi_request is None:
            raise ValueError(f"[{context.transaction_id}] fastapi_request must be provided to InitializeContextPolicy.")

        self.logger.info(
            f"[{context.transaction_id}] Initializing context from request: {fastapi_request.method} {fastapi_request.url}"
        )

        # Read the raw body
        raw_request_body = await fastapi_request.body()
        context.data["raw_request_body"] = raw_request_body

        # Use incoming request URL as initial placeholder
        # Downstream policies (like PrepareBackendHeadersPolicy or a routing policy)
        # will be responsible for setting the final target URL and Host header.
        initial_url = str(fastapi_request.url)

        # Build the initial httpx.Request
        # Pass headers as a list of tuples (bytes, bytes) from the mocked raw attribute
        context.request = httpx.Request(
            method=fastapi_request.method,
            url=initial_url,
            headers=fastapi_request.headers.raw,  # Use raw headers
            params=fastapi_request.query_params,
            content=raw_request_body,
        )

        self.logger.debug(f"[{context.transaction_id}] Initial context.request created with URL: {context.request.url}")

        return context
