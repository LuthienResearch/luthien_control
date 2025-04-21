"""Control Policy for verifying the client API key."""

import logging
from typing import Any, Awaitable, Callable, Optional

from fastapi.responses import JSONResponse
from luthien_control.control_policy.exceptions import (
    ClientAuthenticationError,
    ClientAuthenticationNotFoundError,
    NoRequestError,
)
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.core.context import TransactionContext
from luthien_control.db.database_async import get_main_db_session_cm
from luthien_control.db.sqlmodel_models import ClientApiKey
from sqlalchemy.ext.asyncio import AsyncSession

# Type alias for the database lookup function
ApiKeyLookupFunc = Callable[[AsyncSession, str], Awaitable[Optional[ClientApiKey]]]

logger = logging.getLogger(__name__)

API_KEY_HEADER = "Authorization"
BEARER_PREFIX = "Bearer "


class ClientApiKeyAuthPolicy(ControlPolicy):
    """Verifies the client API key provided in the Authorization header."""

    def __init__(self, api_key_lookup: ApiKeyLookupFunc):
        """Initializes the policy with a function to look up API keys."""
        self._get_api_key_by_value = api_key_lookup
        self.logger = logging.getLogger(__name__)

    async def apply(self, context: TransactionContext) -> TransactionContext:
        """
        Verifies the API key from the Authorization header in the context's FastAPI request.

        Raises:
            NoRequestError: If context.fastapi_request is None.
            ClientAuthenticationError: If the key is missing, invalid, or inactive.

        Args:
            context: The current transaction context.

        Returns:
            The unmodified transaction context if authentication is successful.
        """
        if context.fastapi_request is None:
            raise NoRequestError(f"[{context.transaction_id}] No FastAPI request in context for API key auth.")

        api_key_header_value: Optional[str] = context.fastapi_request.headers.get(API_KEY_HEADER)

        if not api_key_header_value:
            self.logger.warning(f"[{context.transaction_id}] Missing API key in {API_KEY_HEADER} header.")
            context.response = JSONResponse(status_code=401, content={"detail": "Not authenticated: Missing API key."})
            raise ClientAuthenticationNotFoundError(detail="Not authenticated: Missing API key.")

        # Strip "Bearer " prefix if present
        api_key_value = api_key_header_value
        if api_key_value.startswith(BEARER_PREFIX):
            api_key_value = api_key_value[len(BEARER_PREFIX) :]

        # Get a database session and use it to look up the API key
        db_key = None
        async with get_main_db_session_cm() as session:
            db_key = await self._get_api_key_by_value(session, api_key_value)

        if not db_key:
            self.logger.warning(
                f"[{context.transaction_id}] Invalid API key provided (key starts with: {api_key_value[:4]}...)."
            )
            context.response = JSONResponse(status_code=401, content={"detail": "Invalid API Key"})
            raise ClientAuthenticationError(detail="Invalid API Key")

        if not db_key.is_active:
            self.logger.warning(
                f"[{context.transaction_id}] Inactive API key provided (Name: {db_key.name}, ID: {db_key.id})."
            )
            context.response = JSONResponse(status_code=401, content={"detail": "Inactive API Key"})
            raise ClientAuthenticationError(detail="Inactive API Key")

        self.logger.info(
            f"[{context.transaction_id}] Client API key authenticated successfully "
            f"(Name: {db_key.name}, ID: {db_key.id})."
        )
        return context

    def serialize_config(self) -> dict[str, Any]:
        """Serializes config. Returns base info as only dependency is api_key_lookup."""
        return {
            "__policy_type__": self.__class__.__name__,
            "name": self.name,
            "policy_class_path": self.policy_class_path,
        }
