"""Control Policy for adding the API key header to requests."""

import logging
from typing import Optional, cast

from fastapi.responses import JSONResponse
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import ApiKeyNotFoundError, NoRequestError
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction_context import TransactionContext
from sqlalchemy.ext.asyncio import AsyncSession

from .serialization import SerializableDict


class AddApiKeyHeaderPolicy(ControlPolicy):
    """Adds the configured OpenAI API key to the request Authorization header."""

    def __init__(self, name: Optional[str] = None):
        """Initializes the policy."""
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(__name__)

    async def apply(
        self,
        context: TransactionContext,
        container: DependencyContainer,
        session: AsyncSession,
    ) -> TransactionContext:
        """
        Adds the Authorization: Bearer <api_key> header to the context.request.

        Reads OpenAI API key from settings via the container.
        Requires the DependencyContainer and AsyncSession in signature for interface compliance,
        but session is not directly used in this policy's logic.

        Raises:
            NoRequestError if the request is not found in the context.
            ApiKeyNotFoundError if the OpenAI API key is not configured.

        Args:
            context: The current transaction context.
            container: The application dependency container.
            session: An active SQLAlchemy AsyncSession (unused).

        Returns:
            The potentially modified transaction context.
        """
        if context.request is None:
            raise NoRequestError(f"[{context.transaction_id}] No request in context.")
        settings = container.settings
        api_key = settings.get_openai_api_key()
        if not api_key:
            context.response = JSONResponse(
                status_code=500,
                content={"detail": "Server configuration error: OpenAI API key not configured"},
            )
            raise ApiKeyNotFoundError(f"[{context.transaction_id}] OpenAI API key not configured ({self.name}).")
        self.logger.info(f"[{context.transaction_id}] Adding Authorization header for OpenAI key ({self.name}).")
        context.request.headers["Authorization"] = f"Bearer {api_key}"
        return context

    def serialize(self) -> SerializableDict:
        """Serializes config. Returns base info as no instance-specific config needed."""
        return cast(SerializableDict, {"name": self.name})

    @classmethod
    async def from_serialized(cls, config: SerializableDict) -> "AddApiKeyHeaderPolicy":
        """
        Constructs the policy from serialized configuration.

        Args:
            config: Dictionary possibly containing 'name'.

        Returns:
            An instance of AddApiKeyHeaderPolicy.
        """
        instance_name = config.get("name")
        return cls(name=instance_name)
