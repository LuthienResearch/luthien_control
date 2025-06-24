from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction import Transaction
from luthien_control.new_control_policy.control_policy import ControlPolicy
from luthien_control.new_control_policy.serialization import SerializableDict


class SetBackendPolicy(ControlPolicy):
    """A policy that sets the backend URL for the transaction."""

    def __init__(self, name: Optional[str] = None, backend_url: Optional[str] = None):
        super().__init__(name=name)
        self.backend_url = backend_url

    async def apply(self, transaction: Transaction, container: DependencyContainer, session: AsyncSession) -> Transaction:
        transaction.request.api_endpoint = self.backend_url
        return transaction

    def _get_policy_specific_config(self) -> SerializableDict:
        return SerializableDict(
            backend_url=self.backend_url,
        )

    @classmethod
    def from_serialized(cls, config: SerializableDict) -> "SetBackendPolicy":
        """Create a SetBackendPolicy from serialized configuration."""
        name = config.get("name")
        backend_url = config.get("backend_url")
        return cls(name=name, backend_url=backend_url)
