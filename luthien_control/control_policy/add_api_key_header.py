"""Control Policy for adding the API key header to requests."""

import logging
from typing import Optional, cast

from fastapi.responses import JSONResponse
from luthien_control.config.settings import Settings
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import ApiKeyNotFoundError, NoRequestError
from luthien_control.core.transaction_context import TransactionContext

from .serialization import SerializableDict


class AddApiKeyHeaderPolicy(ControlPolicy):
    """Adds the configured API key (e.g., OpenAI) to the request Authorization header."""

    REQUIRED_DEPENDENCIES = ["settings"]

    def __init__(self, settings: Settings, name: Optional[str] = None):
        """Initializes the processor with settings."""
        self.name = name or self.__class__.__name__
        self.settings = settings
        self.logger = logging.getLogger(__name__)

    async def apply(self, context: TransactionContext) -> TransactionContext:
        """
        Adds the Authorization: Bearer <api_key> header to the context.request.

        Reads API key from settings.
        Raises:
            NoRequestError if the request is not found in the context.
            ApiKeyNotFoundError if the API key is not configured.

        Args:
            context: The current transaction context.

        Returns:
            The potentially modified transaction context.
        """
        if context.request is None:
            raise NoRequestError(f"[{context.transaction_id}] No request in context.")
        api_key = self.settings.get_openai_api_key()
        if not api_key:
            context.response = JSONResponse(
                status_code=500, content={"detail": "Server configuration error: API key not configured"}
            )
            raise ApiKeyNotFoundError(f"[{context.transaction_id}] API key not configured ({self.name}).")
        self.logger.info(f"[{context.transaction_id}] Adding Authorization header ({self.name}).")
        context.request.headers["Authorization"] = f"Bearer {api_key}"
        return context

    def serialize(self) -> SerializableDict:
        """Serializes config. Returns base info as only dependency is settings."""
        return cast(SerializableDict, {"name": self.name})

    @classmethod
    async def from_serialized(cls, config: SerializableDict, settings: Settings, **kwargs) -> "AddApiKeyHeaderPolicy":
        """Instantiates the policy from serialized config and dependencies."""
        # Ensure settings dependency is provided correctly via kwargs by loader
        # The 'settings: Settings' type hint ensures it's passed if required by REQUIRED_DEPENDENCIES
        # The loader (`load_policy`) handles injecting it into kwargs based on REQUIRED_DEPENDENCIES.
        return cls(settings=settings, name=config.get("name"))
