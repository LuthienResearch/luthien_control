# Control Policy for verifying the client API key.
#
# MIGRATION NOTE: This policy has been successfully migrated to use the new
# Transaction model by reading the client API key from transaction.request.api_key
# instead of parsing HTTP Authorization headers.

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction import Transaction
from luthien_control.db.client_api_key_crud import get_api_key_by_value
from luthien_control.db.exceptions import LuthienDBQueryError
from luthien_control.new_control_policy.control_policy import ControlPolicy
from luthien_control.new_control_policy.exceptions import (
    ClientAuthenticationError,
    ClientAuthenticationNotFoundError,
    NoRequestError,
)
from luthien_control.new_control_policy.serialization import SerializableDict

logger = logging.getLogger(__name__)

# Constants no longer needed since we read from transaction.request.api_key directly
# API_KEY_HEADER = "Authorization"
# BEARER_PREFIX = "Bearer "


class ClientApiKeyAuthPolicy(ControlPolicy):
    """Verifies the client API key from the transaction's request.

    Attributes:
        name (str): The name of this policy instance.
        logger (logging.Logger): The logger instance for this policy.
    """

    def __init__(self, name: Optional[str] = None):
        """Initializes the policy."""
        self.name = name or self.__class__.__name__
        self.logger = logging.getLogger(__name__)

    async def apply(
        self,
        transaction: Transaction,
        container: DependencyContainer,
        session: AsyncSession,
    ) -> Transaction:
        """
        Verifies the API key from the transaction's request.
        Requires the DependencyContainer and an active SQLAlchemy AsyncSession.

        Raises:
            NoRequestError: If transaction.request is None.
            ClientAuthenticationError: If the key is missing, invalid, or inactive.

        Args:
            transaction: The current transaction.
            container: The application dependency container.
            session: An active SQLAlchemy AsyncSession.

        Returns:
            The unmodified transaction if authentication is successful.
        """
        if transaction.request is None:
            raise NoRequestError("No request in transaction for API key auth.")

        api_key_value = transaction.request.api_key

        if not api_key_value:
            self.logger.warning("Missing API key in transaction request.")
            # In the new model, we raise the error and let the framework handle the response
            raise ClientAuthenticationNotFoundError(detail="Not authenticated: Missing API key.")

        try:
            db_key = await get_api_key_by_value(session, api_key_value)
        except LuthienDBQueryError:
            self.logger.warning(
                f"Invalid API key provided (key starts with: {api_key_value[:4]}...) ({self.__class__.__name__})."
            )
            # In the new model, we raise the error and let the framework handle the response
            raise ClientAuthenticationError(detail="Invalid API Key")

        if not db_key.is_active:
            self.logger.warning(
                f"Inactive API key provided (Name: {db_key.name}, ID: {db_key.id}). ({self.__class__.__name__})."
            )
            # In the new model, we raise the error and let the framework handle the response
            raise ClientAuthenticationError(detail="Inactive API Key")

        self.logger.info(
            f"Client API key authenticated successfully "
            f"(Name: {db_key.name}, ID: {db_key.id}). ({self.__class__.__name__})."
        )

        return transaction

    def get_policy_config(self) -> SerializableDict:
        """Serializes the policy's configuration.

        This method converts the policy's configuration into a serializable
        dictionary. For this policy, only the 'name' attribute is included
        if it has been set to a non-default value.

        Returns:
            SerializableDict: A dictionary representation of the policy's
                              configuration. It may be empty or contain a 'name' key.
        """
        return SerializableDict(name=self.name)

    @classmethod
    def from_serialized(cls, config: SerializableDict) -> "ClientApiKeyAuthPolicy":
        """
        Constructs the policy from serialized data.

        Args:
            config: The serialized configuration dictionary. May optionally
                    contain a 'name' key to set a custom name for the policy instance.

        Returns:
            An instance of ClientApiKeyAuthPolicy.
        """
        instance = cls()  # Name is set to class name by default in __init__

        instance.name = str(config.get("name"))

        return instance
