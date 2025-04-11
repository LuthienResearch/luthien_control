"""Control Policy for initializing the TransactionContext from a FastAPI Request."""

import logging
from typing import Any, Optional

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
    The target URL is initially set to a placeholder.
    Stores the original raw body in context.data["raw_request_body"].
    Extracts the matched route path format and path parameters from the request scope.
    Determines the relative backend path based on the 'full_path' path parameter if present.
    Handles errors during body reading gracefully by logging and storing empty bytes.
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
        if fastapi_request is None:
            raise ValueError(f"[{context.transaction_id}] fastapi_request must be provided to InitializeContextPolicy.")

        self.logger.info(
            f"[{context.transaction_id}] Initializing context from request: "
            f"{fastapi_request.method} {fastapi_request.url}"
        )

        # --- Extract Route and Path Info from Scope ---
        scope = fastapi_request.scope
        path_format = scope.get("route", {}).path_format if scope.get("route") else scope.get("path", "")
        path_params = scope.get("path_params", {})

        context.data["path_format"] = path_format
        context.data["path_params"] = path_params

        # Determine relative path for backend
        # Assumes routes needing proxying have a '{full_path:path}' parameter
        relative_path = path_params.get("full_path", "")

        self.logger.debug(f"[{context.transaction_id}] InitializeContextPolicy Path Params: {path_params}")
        self.logger.debug(f"[{context.transaction_id}] InitializeContextPolicy Derived Relative Path: {relative_path}")

        if relative_path:
            self.logger.debug(
                f"[{context.transaction_id}] Extracted relative path from path_params['full_path']: {relative_path}"
            )
        else:
            # If no 'full_path', assume the request doesn't need standard proxying (e.g., /health)
            # Use the original path minus leading slash as a default, but downstream policies might ignore this.
            relative_path = scope.get("path", "").lstrip("/")
            self.logger.debug(
                f"[{context.transaction_id}] No 'full_path' param found. Using path "
                f"'{relative_path}' as default relative_path."
            )

        self.logger.debug(f"[{context.transaction_id}] InitializeContextPolicy Storing Relative Path: {relative_path}")
        context.data["relative_path"] = relative_path
        # --- End Extract Route and Path Info ---

        # Read the raw body gracefully
        raw_request_body = b""
        try:
            raw_request_body = await fastapi_request.body()
        except Exception as e:
            self.logger.error(f"[{context.transaction_id}] Error reading request body: {e}. Storing empty body.")
            # Store empty bytes if body read fails

        context.data["raw_request_body"] = raw_request_body

        # Downstream policies (like PrepareBackendHeadersPolicy or a routing policy)
        # will be responsible for setting the final target URL and Host header.
        # Set initial URL to something simple, as it will be replaced.
        initial_url = "http://placeholder.internal/"

        # Build the initial httpx.Request
        # Pass headers as a list of tuples (bytes, bytes) from the mocked raw attribute
        context.request = httpx.Request(
            method=fastapi_request.method,
            url=initial_url,
            headers=fastapi_request.headers.raw,  # Use raw headers
            params=fastapi_request.query_params,
            content=raw_request_body,  # Use potentially empty body
        )

        self.logger.debug(f"[{context.transaction_id}] Initial context.request created with URL: {context.request.url}")

        return context

    def serialize_config(self) -> dict[str, Any]:
        """Serializes config. Returns base info as policy takes no parameters."""
        return {
            "__policy_type__": self.__class__.__name__,
            "name": self.name,
            "policy_class_path": self.policy_class_path,
        }
