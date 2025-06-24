# Control Policy for adding the API key header to requests.

from typing import Optional, cast

from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import ApiKeyNotFoundError, NoRequestError
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction import Transaction


class AddApiKeyHeaderPolicy(ControlPolicy):
    """Adds the configured OpenAI API key to the request Authorization header.

    This policy reads the API key from the application settings and adds it
    to the request. It has no policy-specific configuration beyond its name.
    """

    def __init__(self, name: Optional[str] = None):
        """Initializes the policy."""
        super().__init__(name=name)

    async def apply(
        self,
        transaction: Transaction,
        container: DependencyContainer,
        session: AsyncSession,
    ) -> Transaction:
        """
        Sets the API key on the transaction's request.

        Reads OpenAI API key from settings via the container.
        Requires the DependencyContainer and AsyncSession in signature for interface compliance,
        but session is not directly used in this policy's logic.

        Raises:
            NoRequestError if the request is not found in the transaction.
            ApiKeyNotFoundError if the OpenAI API key is not configured.

        Args:
            transaction: The current transaction.
            container: The application dependency container.
            session: An active SQLAlchemy AsyncSession (unused).

        Returns:
            The potentially modified transaction.
        """
        if transaction.request is None:
            raise NoRequestError("No request in transaction.")
        api_key = container.settings.get_openai_api_key()
        if not api_key:
            raise ApiKeyNotFoundError(f"OpenAI API key not configured ({self.name}).")
        self.logger.info(f"Setting API key from settings ({self.name}).")
        transaction.request.api_key = api_key

        return transaction

    def _get_policy_specific_config(self) -> SerializableDict:
        """No additional configuration needed beyond type and name."""
        return {}

    @classmethod
    def from_serialized(cls, config: SerializableDict) -> "AddApiKeyHeaderPolicy":
        """
        Constructs the policy from serialized configuration.

        Args:
            config: Dictionary possibly containing 'name'.

        Returns:
            An instance of AddApiKeyHeaderPolicy.
        """
        instance_name = cast(Optional[str], config.get("name"))
        return cls(name=instance_name)
