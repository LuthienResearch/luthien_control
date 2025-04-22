"""Control Policy for initializing the TransactionContext from a FastAPI Request."""

import logging
from typing import Any, Optional

import httpx
from fastapi import Request
from luthien_control.config.settings import Settings  # Keep for potential future use, or policy config
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.core.transaction_context import TransactionContext


class InitializeContextPolicy(ControlPolicy):
    """
    Initializes the context.request from the incoming FastAPI request.

    Reads the request body and prepares the initial httpx.Request object
    using the method, headers, query parameters, and body from the incoming request.
    """

    def __init__(self, settings: Optional[Settings] = None):  # Settings might not be needed now
        # self.settings = settings # Store if needed for policy config
        self.logger = logging.getLogger(__name__)

    async def apply(self, context: TransactionContext, fastapi_request: Optional[Request] = None) -> TransactionContext:
        """
        Initializes context from fastapi_request, extracting route info.

        Requires fastapi_request to be passed explicitly.
        Raises ValueError if fastapi_request is None.
        """
        context.request = httpx.Request(
            method=fastapi_request.method,
            url=fastapi_request.path_params["full_path"],
            headers=fastapi_request.headers.raw,  # Use raw headers
            params=fastapi_request.query_params,
            content=await fastapi_request.body(),
        )
        return context

    def serialize_config(self) -> dict[str, Any]:
        """Serializes config. Returns base info as policy takes no parameters."""
        return {
            "__policy_type__": self.__class__.__name__,
            "name": self.name,
            "policy_class_path": self.policy_class_path,
        }
