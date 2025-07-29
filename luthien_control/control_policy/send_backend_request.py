import logging
from typing import Any, Dict, Optional

import httpx
import openai
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.api.openai_chat_completions import OpenAIChatCompletionsResponse
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.raw_response import RawResponse
from luthien_control.core.request_type import RequestType
from luthien_control.core.response import Response
from luthien_control.core.streaming_response import OpenAIStreamingIterator, RawStreamingIterator
from luthien_control.core.transaction import Transaction

logger = logging.getLogger(__name__)


class SendBackendRequestPolicy(ControlPolicy):
    """
    Policy responsible for sending requests to the backend.

    For OpenAI chat completions requests, uses the OpenAI SDK.
    For other paths, uses httpx to make direct HTTP calls.

    Attributes:
        name (str): The name of this policy instance, used for logging and
            identification. It defaults to the class name if not provided
            during initialization.
        logger (logging.Logger): The logger instance for this policy.
    """

    name: Optional[str] = Field(default="SendBackendRequestPolicy")

    def _create_debug_info(
        self, backend_url: str, request_payload: Any, error: Exception, api_key: str = ""
    ) -> Dict[str, Any]:
        """Create debug information for backend request failures."""
        debug_info = {
            "backend_url": backend_url,
            "request_model": getattr(request_payload, "model", "unknown"),
            "request_messages_count": len(getattr(request_payload, "messages", [])),
            "error_type": error.__class__.__name__,
            "error_message": str(error),
        }

        # Add OpenAI-specific error details if available
        if hasattr(error, "response") and getattr(error, "response", None) is not None:
            response = getattr(error, "response")
            status_code = getattr(response, "status_code", None)
            debug_info["backend_response"] = {
                "status_code": status_code,
                "headers": dict(getattr(response, "headers", {})),
            }
            # Try to get response body if available
            if hasattr(response, "text"):
                debug_info["backend_response"]["body"] = getattr(response, "text", "")

            # For 404 errors, include identifying characters from the API key
            if status_code == 404 and api_key:
                debug_info["api_key_identifier"] = self._get_api_key_identifier(api_key)

        if hasattr(error, "body") and getattr(error, "body", None) is not None:
            debug_info["backend_error_body"] = getattr(error, "body")

        return debug_info

    def _get_api_key_identifier(self, api_key: str) -> str:
        """Get identifying characters from API key for debugging (first 8 and last 4 chars)."""
        if not api_key:
            return "empty"
        if len(api_key) <= 12:
            return f"{api_key[:4]}...{api_key[-2:]}"
        return f"{api_key[:8]}...{api_key[-4:]}"

    async def apply(
        self,
        transaction: Transaction,
        container: DependencyContainer,
        session: AsyncSession,
    ) -> Transaction:
        """
        Sends requests to the backend using the appropriate method based on transaction type.

        For OpenAI chat completions, uses the OpenAI SDK.
        For raw HTTP requests, uses httpx for direct HTTP calls.

        Args:
            transaction: The current transaction, containing the request to be sent.
            container: The application dependency container, providing settings and OpenAI client.
            session: An active SQLAlchemy AsyncSession. (Unused by this policy but required by the interface).

        Returns:
            The Transaction, updated with the appropriate response.

        Raises:
            ValueError: If backend URL or API key is not configured.
            Various exceptions depending on the backend response.
        """
        if transaction.request_type == RequestType.OPENAI_CHAT:
            return await self._handle_openai_request(transaction, container)
        elif transaction.request_type == RequestType.RAW_PASSTHROUGH:
            return await self._handle_raw_request(transaction, container)
        else:
            raise ValueError("Transaction has no request to process")

    async def _handle_openai_request(self, transaction: Transaction, container: DependencyContainer) -> Transaction:
        """Handle OpenAI chat completions request using the OpenAI SDK."""
        if transaction.openai_request is None:
            raise ValueError("OpenAI request is None")

        # Create OpenAI client for the backend request
        backend_url = transaction.openai_request.api_endpoint
        api_key = transaction.openai_request.api_key

        if not backend_url:
            raise ValueError("Backend URL is not configured")
        if not api_key:
            raise ValueError("OpenAI API key is not configured")

        self.logger.info(f"Creating OpenAI client with backend URL: '{backend_url}' ({self.name})")
        openai_client = container.create_openai_client(backend_url, api_key)

        # Get the structured request payload
        request_payload = transaction.openai_request.payload

        self.logger.info(
            f"Sending chat completions request to backend with model '{request_payload.model}' "
            f"and {len(request_payload.messages)} messages. ({self.name}); "
            f"Target url: {backend_url}"
        )

        try:
            # Send request using OpenAI SDK
            # Use the request payload directly - the OpenAI SDK should accept our Pydantic model
            request_dict = request_payload.model_dump()
            # Remove any None values to avoid issues with the OpenAI SDK
            request_dict = {k: v for k, v in request_dict.items() if v is not None}

            backend_response = await openai_client.chat.completions.create(**request_dict)

            # Check if this is a streaming response
            if hasattr(backend_response, "model_dump") and callable(getattr(backend_response, "model_dump")):
                # Regular response - convert to our structured response model
                response_payload = OpenAIChatCompletionsResponse.model_validate(backend_response.model_dump())

                # Store the structured response in the transaction
                if transaction.openai_response is None:
                    transaction.openai_response = Response()
                transaction.openai_response.payload = response_payload
                transaction.openai_response.api_endpoint = backend_url

                self.logger.info(
                    f"Received backend response with {len(response_payload.choices)} choices "
                    f"and usage: {response_payload.usage}. ({self.name})"
                )
            else:
                # Streaming response - wrap it in our streaming iterator
                self.logger.info(f"Received streaming backend response. ({self.name})")

                # Create streaming iterator wrapper
                streaming_iterator = OpenAIStreamingIterator(backend_response)

                # Create response object with streaming iterator
                if transaction.openai_response is None:
                    transaction.openai_response = Response()
                transaction.openai_response.api_endpoint = backend_url
                transaction.openai_response.streaming_iterator = streaming_iterator
                # Note: payload is left as None for streaming responses

        except openai.NotFoundError as e:
            self.logger.error(
                f"OpenAI NotFoundError during backend request with base url {backend_url}: {e} ({self.name})"
            )
            raise
        except openai.APITimeoutError as e:
            self.logger.error(f"Timeout error during backend request: {e} ({self.name})")
            # Store debug information for potential dev mode access
            debug_info = self._create_debug_info(backend_url, request_payload, e, api_key)
            e.debug_info = debug_info  # type: ignore
            raise
        except openai.APIConnectionError as e:
            self.logger.error(f"Connection error during backend request: {e} ({self.name})")
            # Store debug information for potential dev mode access
            debug_info = self._create_debug_info(backend_url, request_payload, e, api_key)
            e.debug_info = debug_info  # type: ignore
            raise
        except openai.APIError as e:
            self.logger.error(f"OpenAI API error during backend request: {e} ({self.name})")
            # Store debug information for potential dev mode access
            debug_info = self._create_debug_info(backend_url, request_payload, e, api_key)
            e.debug_info = debug_info  # type: ignore
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error during backend request: {e} ({self.name})")
            # Store debug information for potential dev mode access
            debug_info = self._create_debug_info(backend_url, request_payload, e, api_key)
            e.debug_info = debug_info  # type: ignore
            raise

        return transaction

    async def _handle_raw_request(self, transaction: Transaction, container: DependencyContainer) -> Transaction:
        """Handle raw HTTP request using httpx."""
        if transaction.raw_request is None:
            raise ValueError("Raw request is None")

        raw_request = transaction.raw_request
        if raw_request.backend_url is None:
            raise ValueError("Raw request has no backend URL")
        backend_url = raw_request.backend_url

        # Build the full URL
        full_url = f"{backend_url.rstrip('/')}/{raw_request.path.lstrip('/')}"

        self.logger.info(f"Sending {raw_request.method} request to {full_url} ({self.name})")

        # Prepare headers
        headers = raw_request.headers.copy()
        if raw_request.api_key:
            headers["Authorization"] = f"Bearer {raw_request.api_key}"

        try:
            async with httpx.AsyncClient() as client:
                # Check if the request indicates streaming (e.g., Accept: text/event-stream)
                is_streaming_request = headers.get("Accept") == "text/event-stream"

                if is_streaming_request:
                    # Handle streaming response
                    async with client.stream(
                        method=raw_request.method, url=full_url, headers=headers, content=raw_request.body
                    ) as response:
                        # Create streaming iterator
                        streaming_iterator = RawStreamingIterator(response)

                        # Store the streaming response
                        transaction.raw_response = RawResponse(
                            status_code=response.status_code,
                            headers=dict(response.headers),
                            streaming_iterator=streaming_iterator,
                        )

                        self.logger.info(
                            f"Received streaming raw response with status {response.status_code} ({self.name})"
                        )
                else:
                    # Handle regular response
                    response = await client.request(
                        method=raw_request.method, url=full_url, headers=headers, content=raw_request.body
                    )

                    # Store the raw response
                    transaction.raw_response = RawResponse(
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        body=response.content,
                        content=response.text if response.text else None,
                    )

                    self.logger.info(f"Received raw response with status {response.status_code} ({self.name})")

        except httpx.TimeoutException as e:
            self.logger.error(f"Timeout error during raw request: {e} ({self.name})")
            raise
        except httpx.ConnectError as e:
            self.logger.error(f"Connection error during raw request: {e} ({self.name})")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error during raw request: {e} ({self.name})")
            raise

        return transaction
