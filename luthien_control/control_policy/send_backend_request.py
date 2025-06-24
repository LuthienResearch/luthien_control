import logging
from typing import Optional

import openai
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.api.openai_chat_completions import OpenAIChatCompletionsResponse
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import NoRequestError
from luthien_control.control_policy.serialization import SerializableDict
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

    def __init__(self, name: Optional[str] = None):
        super().__init__(name=name)

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
            NoRequestError: If transaction.request is None.
            openai.APIError: For API-related errors from the OpenAI backend.
            openai.APITimeoutError: If the request to the backend times out.
            openai.APIConnectionError: For network-related issues during the backend request.
            Exception: For any other unexpected errors during request execution.
        """
        if transaction.request is None:
            raise NoRequestError("No request in transaction for backend request.")

        # Create OpenAI client for the backend request
        backend_url = transaction.request.api_endpoint
        api_key = transaction.request.api_key

        if not backend_url:
            raise ValueError("Backend URL is not configured")
        if not api_key:
            raise ValueError("OpenAI API key is not configured")

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
            raise
        except openai.APIConnectionError as e:
            self.logger.error(f"Connection error during backend request: {e} ({self.name})")
            raise
        except openai.APIError as e:
            self.logger.error(f"OpenAI API error during backend request: {e} ({self.name})")
            raise
        except Exception as e:
            self.logger.exception(f"Unexpected error during backend request: {e} ({self.name})")
            raise

        return transaction

    def _get_policy_specific_config(self) -> SerializableDict:
        """No additional configuration needed beyond type and name."""
        return {}

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
        return cls(name=resolved_name)
