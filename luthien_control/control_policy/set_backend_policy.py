from typing import Optional

from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.request_type import RequestType
from luthien_control.core.transaction import Transaction


class SetBackendPolicy(ControlPolicy):
    """A policy that sets the backend URL for the transaction."""

    name: Optional[str] = Field(default="SetBackendPolicy")
    backend_url: Optional[str] = Field(default=None)

    async def apply(
        self, transaction: Transaction, container: DependencyContainer, session: AsyncSession
    ) -> Transaction:
        if self.backend_url is not None:
            # Handle both OpenAI and raw request types
            if transaction.request_type == RequestType.OPENAI_CHAT:
                assert transaction.openai_request is not None
                # Set the base URL only - the OpenAI client will append the specific endpoint path
                # The original api_endpoint (e.g., "v1/chat/completions") will be used by the OpenAI client
                transaction.openai_request.api_endpoint = self.backend_url
            elif transaction.request_type == RequestType.RAW_PASSTHROUGH:
                assert transaction.raw_request is not None
                # For raw requests, set the backend_url field which will be used by SendBackendRequestPolicy
                transaction.raw_request.backend_url = self.backend_url
        return transaction

    def _get_policy_specific_config(self) -> SerializableDict:
        """Return policy-specific configuration for backward compatibility with tests."""
        return SerializableDict(
            backend_url=self.backend_url,
        )
