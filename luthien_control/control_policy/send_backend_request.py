"""Core control policy implementations."""

import logging
from typing import Optional, cast
from urllib.parse import urlparse

import httpx
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction_context import TransactionContext
from luthien_control.settings import Settings
from sqlalchemy.ext.asyncio import AsyncSession

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
        self.name: str = name or self.__class__.__name__

    def _build_target_url(self, base_url: str, relative_path: str) -> str:
        """Constructs the full target URL for the backend request."""
        # Ensure no double slashes
        target_url = f"{base_url.rstrip('/')}/{relative_path.lstrip('/')}"
        logger.debug(f"Constructed target URL: {target_url} (from base: {base_url}, relative: {relative_path})")
        return target_url

    def _prepare_backend_headers(self, context: TransactionContext, settings: Settings) -> list[tuple[bytes, bytes]]:
        """Prepares the headers to be sent to the backend.

        Args:
            context: The current transaction context, containing the original request.
            settings: The application settings, used to get the backend URL
                and API key.

        Returns:
            A list of (header_name, header_value) tuples for the backend request.

        Raises:
            ValueError: If the BACKEND_URL setting is invalid and its hostname
                cannot be parsed for the Host header.
        """
        original_request = context.request
        backend_headers: list[tuple[bytes, bytes]] = []
        backend_url_base = settings.get_backend_url()

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
            raise ValueError(f"Could not determine backend Host from BACKEND_URL: {e}")

        # Force Accept-Encoding: identity (avoids downstream decompression issues)
        backend_headers.append((b"accept-encoding", b"identity"))

        # Add Backend Authorization Header using passed settings
        openai_key = settings.get_openai_api_key()
        backend_headers.append((b"authorization", f"Bearer {openai_key}".encode("latin-1")))

        return backend_headers

    async def apply(
        self,
        context: TransactionContext,
        container: DependencyContainer,
        session: AsyncSession,  # session is unused but required by interface
    ) -> TransactionContext:
        """
        Sends the request from context to the backend and stores the response.

        This policy constructs the target URL, prepares headers, and uses the
        HTTP client from the `DependencyContainer` to send the `context.request`.
        The backend's response (an `httpx.Response` object) is stored in
        `context.data["backend_response"]`. The response body is read immediately.

        Args:
            context: The current transaction context, containing the `request` to be sent.
            container: The application dependency container, providing `settings` and `http_client`.
            session: An active SQLAlchemy `AsyncSession`. (Unused by this policy but required by the interface).

        Returns:
            The `TransactionContext`, updated with `context.data["backend_response"]`
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

        # --- Prepare Request Components ---
        try:
            target_url = self._build_target_url(backend_url_base, context.request.url.path)
            backend_headers = self._prepare_backend_headers(context, settings)
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
            response = await http_client.send(context.request)
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
        """Serializes the policy's configuration.

        For this policy, only the 'name' attribute is included, as all other
        dependencies (like HTTP client, settings) are resolved from the
        DependencyContainer at runtime.

        Returns:
            SerializableDict: A dictionary containing the 'name' of the policy instance.
        """
        return cast(SerializableDict, {"name": self.name})

    @classmethod
    async def from_serialized(cls, config: SerializableDict) -> "SendBackendRequestPolicy":
        """
        Constructs the policy from serialized configuration.

        Args:
            config: A dictionary that may optionally contain a 'name' key
                    to set a custom name for the policy instance.

        Returns:
            An instance of SendBackendRequestPolicy.
        """
        return cls(name=config.get("name"))
