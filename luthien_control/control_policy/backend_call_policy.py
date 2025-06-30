import os

import openai
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction import Transaction
from luthien_control.utils.backend_call_spec import BackendCallSpec


class BackendCallPolicy(ControlPolicy):
    """
    This policy makes a backend LLM call.
    """

    backend_call_spec: BackendCallSpec = Field(...)

    async def apply(
        self,
        transaction: Transaction,
        container: DependencyContainer,
        session: AsyncSession,
    ) -> Transaction:
        api_key = os.environ.get(self.backend_call_spec.api_key_env_var)
        if api_key:
            transaction.request.api_key = api_key
        transaction.request.api_endpoint = self.backend_call_spec.api_endpoint

        # Update the request payload with all arguments from backend_call_spec.request_args
        # Use model_validate to properly handle nested pydantic models and EventedList/EventedDict
        if self.backend_call_spec.request_args:
            current_data = transaction.request.payload.model_dump()
            current_data.update(self.backend_call_spec.request_args)
            transaction.request.payload = transaction.request.payload.__class__.model_validate(current_data)

        # Set the model if specified
        if self.backend_call_spec.model:
            transaction.request.payload.model = self.backend_call_spec.model

        openai_client = container.create_openai_client(
            transaction.request.api_endpoint, api_key or transaction.request.api_key
        )
        try:
            response_payload = await openai_client.chat.completions.create(**transaction.request.payload.model_dump())
            transaction.response.payload = response_payload
            transaction.response.api_endpoint = transaction.request.api_endpoint
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
