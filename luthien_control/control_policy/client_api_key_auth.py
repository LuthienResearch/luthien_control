"""Control Policy for verifying the client API key."""

import logging
from typing import TYPE_CHECKING, Optional, cast

from fastapi.responses import JSONResponse
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import (
    ClientAuthenticationError,
    ClientAuthenticationNotFoundError,
    NoRequestError,
)
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.transaction_context import TransactionContext
from luthien_control.db.database_async import get_db_session

# Import the function to fetch API key by value
from luthien_control.db.client_api_key_crud import get_api_key_by_value

# Import the centralized type definition - REMOVED as ApiKeyLookupFunc is no longer used here
# from luthien_control.types import ApiKeyLookupFunc

if TYPE_CHECKING:
    pass  # Keep if needed for other forward refs, otherwise remove

logger = logging.getLogger(__name__)

API_KEY_HEADER = "Authorization"
BEARER_PREFIX = "Bearer "


class ClientApiKeyAuthPolicy(ControlPolicy):
    """Verifies the client API key provided in the Authorization header."""

    REQUIRED_DEPENDENCIES = []  # Removed "api_key_lookup"

    def __init__(self, name: Optional[str] = None):  # Removed api_key_lookup parameter
        """Initializes the policy."""
        self.logger = logging.getLogger(__name__)
        self.name = name or self.__class__.__name__
        # Removed self._api_key_lookup assignment

    async def apply(self, context: TransactionContext) -> TransactionContext:
        """
        Verifies the API key from the Authorization header in the context's request.

        Raises:
            NoRequestError: If context.fastapi_request is None.
            ClientAuthenticationError: If the key is missing, invalid, or inactive.

        Args:
            context: The current transaction context.

        Returns:
            The unmodified transaction context if authentication is successful.
        """
        if context.request is None:
            raise NoRequestError(f"[{context.transaction_id}] No request in context for API key auth.")

        api_key_header_value: Optional[str] = context.request.headers.get(API_KEY_HEADER)

        if not api_key_header_value:
            self.logger.warning(f"[{context.transaction_id}] Missing API key in {API_KEY_HEADER} header.")
            context.response = JSONResponse(status_code=401, content={"detail": "Not authenticated: Missing API key."})
            raise ClientAuthenticationNotFoundError(detail="Not authenticated: Missing API key.")

        # Strip "Bearer " prefix if present
        api_key_value = api_key_header_value
        if api_key_value.startswith(BEARER_PREFIX):
            api_key_value = api_key_value[len(BEARER_PREFIX) :]

        # Use the imported get_api_key_by_value function with a session
        async with get_db_session() as session:
            db_key = await get_api_key_by_value(session, api_key_value)  # Changed from self._api_key_lookup

        if not db_key:
            self.logger.warning(
                f"[{context.transaction_id}] Invalid API key provided "
                f"(key starts with: {api_key_value[:4]}...) ({self.name})."
            )
            context.response = JSONResponse(status_code=401, content={"detail": "Invalid API Key"})
            raise ClientAuthenticationError(detail="Invalid API Key")

        if not db_key.is_active:
            self.logger.warning(
                f"[{context.transaction_id}] Inactive API key provided "
                f"(Name: {db_key.name}, ID: {db_key.id}). ({self.name})."
            )
            context.response = JSONResponse(status_code=401, content={"detail": "Inactive API Key"})
            raise ClientAuthenticationError(detail="Inactive API Key")

        self.logger.info(
            f"[{context.transaction_id}] Client API key authenticated successfully "
            f"(Name: {db_key.name}, ID: {db_key.id}). ({self.name})."
        )
        context.response = None  # Clear any previous error response set above
        # Store client identity in context?
        context.client_identity = {"api_key_name": db_key.name, "api_key_id": db_key.id}
        return context

    def serialize(self) -> SerializableDict:
        """Serializes config. Only includes name as no other config is needed."""
        return cast(SerializableDict, {"name": self.name})

    @classmethod
    async def from_serialized(cls, config: SerializableDict, **kwargs) -> "ClientApiKeyAuthPolicy":
        """
        Constructs the policy from serialized data.

        Args:
            config: The serialized configuration (expects 'name').
            **kwargs: Dictionary possibly containing dependencies (ignored).

        Returns:
            An instance of ClientApiKeyAuthPolicy.
        """
        return cls(name=config.get("name"))
