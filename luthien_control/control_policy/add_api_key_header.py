"""Control Policy for adding the API key header to requests."""

import logging
from typing import Any

from fastapi.responses import JSONResponse
from luthien_control.config.settings import Settings
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import ApiKeyNotFoundError, NoRequestError
from luthien_control.core.transaction_context import TransactionContext


class AddApiKeyHeaderPolicy(ControlPolicy):
    """Adds the configured API key (e.g., OpenAI) to the request Authorization header."""

    def __init__(self, settings: Settings):
        """Initializes the processor with settings."""
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
            raise ApiKeyNotFoundError(f"[{context.transaction_id}] API key not configured.")
        self.logger.info(f"[{context.transaction_id}] Adding Authorization header.")
        context.request.headers["Authorization"] = f"Bearer {api_key}"
        return context

    def serialize_config(self) -> dict[str, Any]:
        """Serializes config. Returns base info as only dependency is settings."""
        return {
            "__policy_type__": self.__class__.__name__,
            "name": self.name,
            "policy_class_path": self.policy_class_path,
        }
