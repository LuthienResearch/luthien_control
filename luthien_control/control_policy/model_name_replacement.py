from typing import Dict

from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import NoRequestError
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction import Transaction


class ModelNameReplacementPolicy(ControlPolicy):
    """Replaces model names in requests based on a configured mapping.

    This policy allows clients to use fake model names that will be
    replaced with real model names before the request is sent to the backend.
    This is useful for services like Cursor that assume model strings that match
    known models must route through specific endpoints.
    """

    name: str = Field(default="ModelNameReplacementPolicy")
    model_mapping: Dict[str, str] = Field(default_factory=dict)

    async def apply(
        self,
        transaction: Transaction,
        container: DependencyContainer,
        session: AsyncSession,
    ) -> Transaction:
        """
        Replaces the model name in the request payload based on the configured mapping.

        Args:
            transaction: The current transaction.
            container: The application dependency container.
            session: An active SQLAlchemy AsyncSession (unused).

        Returns:
            The potentially modified transaction.

        Raises:
            NoRequestError: If no request is found in the transaction.
        """
        if transaction.request is None:
            raise NoRequestError("No request in transaction.")

        if hasattr(transaction.request.payload, "model"):
            original_model = transaction.request.payload.model

            if original_model in self.model_mapping:
                new_model = self.model_mapping[original_model]
                self.logger.info(f"Replacing model name: {original_model} -> {new_model}")
                transaction.request.payload.model = new_model

        return transaction
