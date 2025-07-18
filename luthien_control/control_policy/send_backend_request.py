import logging
from typing import Any, Dict, Optional

import openai
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.api.openai_chat_completions import OpenAIChatCompletionsResponse
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction import Transaction

logger = logging.getLogger(__name__)


class SendBackendRequestPolicy(ControlPolicy):
    """
    Policy responsible for sending the chat completions request to the OpenAI-compatible backend
    using the OpenAI SDK and storing the structured response.

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
        Sends the chat completions request to the OpenAI-compatible backend using the OpenAI SDK.

        This policy uses the OpenAI SDK to send the structured chat completions request
        from transaction.request.payload to the backend API endpoint. The response
        is stored as a structured OpenAIChatCompletionsResponse in transaction.response.payload.

        Args:
            transaction: The current transaction, containing the request payload to be sent.
            container: The application dependency container, providing settings and OpenAI client.
            session: An active SQLAlchemy AsyncSession. (Unused by this policy but required by the interface).

        Returns:
            The Transaction, updated with transaction.response.payload containing the
            OpenAIChatCompletionsResponse from the backend.

        Raises:
            ValueError: If backend URL or API key is not configured.
            openai.APIError: For API-related errors from the OpenAI backend.
            openai.APITimeoutError: If the request to the backend times out.
            openai.APIConnectionError: For network-related issues during the backend request.
            Exception: For any other unexpected errors during request execution.
        """
        # Create OpenAI client for the backend request
        backend_url = transaction.request.api_endpoint
        api_key = transaction.request.api_key

        if not backend_url:
            raise ValueError("Backend URL is not configured")
        if not api_key:
            raise ValueError("OpenAI API key is not configured")

        self.logger.info(f"Creating OpenAI client with backend URL: '{backend_url}' ({self.name})")
        openai_client = container.create_openai_client(backend_url, api_key)

        # Get the structured request payload
        request_payload = transaction.request.payload

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

            # Convert OpenAI SDK response to our structured response model
            response_payload = OpenAIChatCompletionsResponse.model_validate(backend_response.model_dump())

            # Store the structured response in the transaction
            transaction.response.payload = response_payload
            transaction.response.api_endpoint = backend_url

            self.logger.info(
                f"Received backend response with {len(response_payload.choices)} choices "
                f"and usage: {response_payload.usage}. ({self.name})"
            )

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
