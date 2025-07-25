import logging
from typing import Optional

from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import (
    ClientAuthenticationError,
    ClientAuthenticationNotFoundError,
    NoRequestError,
)
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction import Transaction
from luthien_control.db.client_api_key_crud import get_api_key_by_value
from luthien_control.db.exceptions import LuthienDBQueryError

logger = logging.getLogger(__name__)


class ClientApiKeyAuthPolicy(ControlPolicy):
    """Verifies the client API key from the transaction's request.

    This policy authenticates clients by checking their API key against
    the database. It ensures the key exists and is active.

    Attributes:
        name (str): The name of this policy instance.
    """

    name: Optional[str] = Field(default="ClientApiKeyAuthPolicy")

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
            raise ClientAuthenticationNotFoundError(detail="Not authenticated: Missing API key.")

        try:
            db_key = await get_api_key_by_value(session, api_key_value)
        except LuthienDBQueryError:
            self.logger.warning(
                f"Invalid API key provided (key starts with: {api_key_value[:4]}...) ({self.__class__.__name__})."
            )
            raise ClientAuthenticationError(detail="Invalid API Key")

        if not db_key.is_active:
            self.logger.warning(
                f"Inactive API key provided (Name: {db_key.name}, ID: {db_key.id}). ({self.__class__.__name__})."
            )
            raise ClientAuthenticationError(detail="Inactive API Key")

        self.logger.info(
            f"Client API key authenticated successfully "
            f"(Name: {db_key.name}, ID: {db_key.id}). ({self.__class__.__name__})."
        )

        return transaction
