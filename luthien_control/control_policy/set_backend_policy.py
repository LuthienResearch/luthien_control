from typing import Optional

from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction import Transaction


class SetBackendPolicy(ControlPolicy):
    """A policy that sets the backend URL for the transaction."""

    backend_url: Optional[str] = Field(default=None)

    async def apply(
        self, transaction: Transaction, container: DependencyContainer, session: AsyncSession
    ) -> Transaction:
        if self.backend_url is not None:
            transaction.request.api_endpoint = self.backend_url
        return transaction
