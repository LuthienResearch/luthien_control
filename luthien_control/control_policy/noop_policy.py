from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction_context import TransactionContext


class NoopPolicy(ControlPolicy):
    """A policy that does nothing."""

    def __init__(self, name: str = "NoopPolicy"):
        self.name = name

    async def apply(
        self, context: TransactionContext, container: DependencyContainer, session: AsyncSession
    ) -> TransactionContext:
        return context

    def serialize(self) -> SerializableDict:
        return SerializableDict(name=self.name)

    @classmethod
    def from_serialized(cls, config: SerializableDict) -> "NoopPolicy":
        return cls(name=str(config.get("name", cls.__name__)))
