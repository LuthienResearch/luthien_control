from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction import Transaction
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.serialization import SerializableDict


class NoopPolicy(ControlPolicy):
    """A policy that does nothing.

    This is the simplest possible policy implementation. It passes through
    the transaction unchanged and has no policy-specific configuration beyond
    its name.
    """

    def __init__(self, name: Optional[str] = None):
        super().__init__(name=name)

    async def apply(
        self, transaction: Transaction, container: DependencyContainer, session: AsyncSession
    ) -> Transaction:
        """Simply returns the transaction unchanged."""
        return transaction

    def _get_policy_specific_config(self) -> SerializableDict:
        """No additional configuration needed beyond type and name."""
        return {}

    @classmethod
    def from_serialized(cls, config: SerializableDict) -> "NoopPolicy":
        """Reconstruct from serialized form. Only needs to extract the name."""
        name = config.get("name")
        return cls(name=str(name) if name is not None else None)
