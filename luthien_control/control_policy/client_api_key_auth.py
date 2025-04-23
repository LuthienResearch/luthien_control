"""Control Policy for verifying the client API key."""

import logging
from typing import Awaitable, Callable, Optional, cast

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
from luthien_control.db.sqlmodel_models import ClientApiKey
from sqlalchemy.ext.asyncio import AsyncSession

# Type alias for the database lookup function
ApiKeyLookupFunc = Callable[[AsyncSession, str], Awaitable[Optional[ClientApiKey]]]

logger = logging.getLogger(__name__)

API_KEY_HEADER = "Authorization"
BEARER_PREFIX = "Bearer "


class ClientApiKeyAuthPolicy(ControlPolicy):
    """Verifies the client API key provided in the Authorization header."""

    REQUIRED_DEPENDENCIES = ["api_key_lookup"]

    def __init__(self, api_key_lookup: ApiKeyLookupFunc):
        """Initializes the policy with a function to look up API keys."""
        self.logger = logging.getLogger(__name__)
        self._api_key_lookup = api_key_lookup

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

        # Use the lookup function stored during init, assuming it doesn't need the session
        # based on the type hint definition used by the dependency injector.
        # The injected _api_key_lookup function expects the session as the first argument
        # We need to obtain an async session here.
        # TODO: Review if the session should be passed differently or if the lookup function signature should change
        # For now, get a new session.
        async with get_db_session() as session:
            db_key = await self._api_key_lookup(session, api_key_value)

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
        context.response = None  # Clear any previous error response set above
        # Store client identity in context?
        context.client_identity = {"api_key_name": db_key.name, "api_key_id": db_key.id}
        return context

    def serialize(self) -> SerializableDict:
        """Serializes config. Returns empty dict as dependency is injected."""
        # No configuration needed, the loader injects the api_key_lookup
        return cast(SerializableDict, {})

    @classmethod
    def from_serialized(cls, config: SerializableDict, **kwargs) -> "ClientApiKeyAuthPolicy":
        """
        Constructs the policy, extracting the api_key_lookup function from kwargs.

        Args:
            config: The serialized configuration (expected to be empty).
            **kwargs: Dictionary possibly containing dependencies (expects 'api_key_lookup').

        Returns:
            An instance of ClientApiKeyAuthPolicy.

        Raises:
            TypeError: If 'api_key_lookup' is missing in kwargs or not callable.
        """
        api_key_lookup = kwargs.get("api_key_lookup")
        if not callable(api_key_lookup):
            raise TypeError(
                "ClientApiKeyAuthPolicy requires 'api_key_lookup' in dependencies" + f" got: {type(api_key_lookup)}"
            )
        # The config dict is ignored for this policy as there are no parameters
        # Pass the extracted dependency to the constructor
        return cls(api_key_lookup=api_key_lookup)
