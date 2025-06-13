# Core control policy implementations.

import logging
from typing import Optional, cast
from urllib.parse import urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.tracked_context import TrackedContext
from luthien_control.settings import Settings

logger = logging.getLogger(__name__)


class SendBackendRequestPolicy(ControlPolicy):
    """
    Policy responsible for sending the request to the backend, storing the response,
    and reading the raw response body.

    Attributes:
        name (str): The name of this policy instance, used for logging and
            identification. It defaults to the class name if not provided
            during initialization.
    """

    _EXCLUDED_BACKEND_HEADERS = {
        b"host",
        b"transfer-encoding",
        b"accept-encoding",  # We force identity
        b"authorization",  # We add our own
    }

    def __init__(self, name: Optional[str] = None):
        self.name = name or self.__class__.__name__

    def _build_target_url(self, base_url: str, relative_path: str) -> str:
        """Constructs the full target URL for the backend request."""
        # Ensure no double slashes
        target_url = f"{base_url.rstrip('/')}/{relative_path.lstrip('/')}"
        logger.debug(f"Constructed target URL: {target_url} (from base: {base_url}, relative: {relative_path})")
        return target_url

    def _prepare_backend_headers(self, context: TrackedContext, settings: Settings) -> dict[str, str]:
        """Prepares the headers to be sent to the backend.

        Args:
            context: The current transaction context, containing the original request.
            settings: The application settings, used to get the backend URL
                and API key.

        Returns:
            A dictionary of header name to value mappings for the backend request.

        Raises:
            ValueError: If the BACKEND_URL setting is invalid and its hostname
                cannot be parsed for the Host header.
        """
        if context.request is None:
            raise ValueError("No request in context")

        backend_headers: dict[str, str] = {}
        backend_url_base = settings.get_backend_url()

        # Excluded headers converted to string format for easier comparison
        excluded_headers = {"host", "transfer-encoding", "accept-encoding", "authorization"}

        # Copy necessary headers from original request, excluding problematic ones
        for header_name, header_value in context.request.headers.items():
            if header_name.lower() not in excluded_headers:
                backend_headers[header_name] = header_value

        # Add the correct Host header for the backend
        try:
            parsed_backend_url = urlparse(backend_url_base)
            backend_host_nullable: Optional[str] = cast(Optional[str], parsed_backend_url.hostname)

            if not backend_host_nullable:
                raise ValueError("Could not parse hostname from BACKEND_URL")
            backend_headers["Host"] = backend_host_nullable
        except ValueError as e:
            logger.error(
                f"[{context.transaction_id}] Invalid BACKEND_URL '{backend_url_base}' for Host header parsing: {e}",
                extra={"request_id": context.transaction_id},
            )
            raise ValueError(f"Could not determine backend Host from BACKEND_URL: {e}")

        # Force Accept-Encoding: identity (avoids downstream decompression issues)
        backend_headers["Accept-Encoding"] = "identity"

        # Add Backend Authorization Header using passed settings
        openai_key = settings.get_openai_api_key()
        backend_headers["Authorization"] = f"Bearer {openai_key}"

        return backend_headers

    async def apply(
        self,
        context: TrackedContext,
        container: DependencyContainer,
        session: AsyncSession,  # session is unused but required by interface
    ) -> TrackedContext:
        """
        Sends the request from context to the backend and stores the response.

        This policy constructs the target URL, prepares headers, and uses the
        HTTP client from the `DependencyContainer` to send the `context.request`.
        The backend's response (an `httpx.Response` object) is stored in
        `context.response`. The response body is read immediately.

        Args:
            context: The current transaction context, containing the `request` to be sent.
            container: The application dependency container, providing `settings` and `http_client`.
            session: An active SQLAlchemy `AsyncSession`. (Unused by this policy but required by the interface).

        Returns:
            The `TrackedContext`, updated with `context.response`
            containing the `httpx.Response` from the backend.

        Raises:
            ValueError: If `context.request` is None or if `BACKEND_URL` is invalid.
            httpx.TimeoutException: If the request to the backend times out.
            httpx.RequestError: For other network-related issues during the backend request.
            Exception: For any other unexpected errors during request preparation or execution.
        """
        settings = container.settings
        http_client = container.http_client

        if not context.request:
            raise ValueError(f"[{context.transaction_id}] Cannot send request: context.request is None")

        backend_url_base = settings.get_backend_url()
        if backend_url_base is None:
            error_msg = f"[{context.transaction_id}] BACKEND_URL is not configured."
            logger.error(error_msg)
            raise ValueError(error_msg)

        # --- Prepare Request Components ---
        try:
            # Extract path from current URL
            current_url = context.request.url
            parsed_url = urlparse(str(current_url))
            target_url = self._build_target_url(backend_url_base, parsed_url.path)
            backend_headers = self._prepare_backend_headers(context, settings)

            # Update request with backend URL and headers
            context.update_request(headers=backend_headers)

        except ValueError as e:
            # Configuration or header preparation error
            logger.error(
                f"[{context.transaction_id}] Error preparing backend request components: {e}",
                extra={"request_id": context.transaction_id},
            )
            raise  # Re-raise the configuration error

        # --- Send Backend Request ---
        try:
            # Build httpx.Request from TrackedRequest
            httpx_request = httpx.Request(
                method=context.request.method, url=target_url, headers=backend_headers, content=context.request.content
            )

            logger.debug(
                f"[{context.transaction_id}] Sending request to backend: {httpx_request.method} {httpx_request.url}"
            )
            response = await http_client.send(httpx_request)
            # Read response body immediately to ensure connection is closed
            await response.aread()

            # Store response in TrackedContext
            context.update_response(
                status_code=response.status_code, headers=dict(response.headers), content=response.content
            )

            logger.debug(f"[{context.transaction_id}] Received backend response: {response.status_code}")
            logger.debug(f"[{context.transaction_id}] Read {len(response.content)} bytes from backend response body.")

        except (httpx.TimeoutException, httpx.RequestError) as e:
            error_type = type(e).__name__
            logger.error(
                f"[{context.transaction_id}] {error_type} connecting to backend '{target_url}': {e}",
                extra={"request_id": context.transaction_id},
            )
            raise  # Re-raise the httpx error
        except Exception as e:
            logger.exception(
                f"[{context.transaction_id}] Unexpected error during backend request "
                f"to '{target_url}' or body read: {e}",
                extra={"request_id": context.transaction_id},
            )
            raise  # Re-raise the unexpected error

        return context

    def serialize(self) -> SerializableDict:
        """Serializes the policy's configuration.

        For this policy, only the 'name' attribute is included, as all other
        dependencies (like HTTP client, settings) are resolved from the
        DependencyContainer at runtime.

        Returns:
            SerializableDict: A dictionary containing the 'name' of the policy instance.
        """
        return cast(SerializableDict, {"name": self.name})

    @classmethod
    def from_serialized(cls, config: SerializableDict) -> "SendBackendRequestPolicy":
        """
        Constructs the policy from serialized configuration.

        Args:
            config: A dictionary that may optionally contain a 'name' key
                    to set a custom name for the policy instance.

        Returns:
            An instance of SendBackendRequestPolicy.
        """
        resolved_name = str(config.get("name", cls.__name__))
        # If name_val is None, resolved_name remains None, and __init__ will use default.
        return cls(name=resolved_name)
