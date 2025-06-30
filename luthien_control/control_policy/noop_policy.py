
from pydantic import field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction import Transaction


class NoopPolicy(ControlPolicy):
    """A policy that does nothing.

    This is the simplest possible policy implementation. It passes through
    the transaction unchanged and has no policy-specific configuration beyond
    its name.
    """

    @field_validator('name', mode='before')
    @classmethod
    def validate_name(cls, value):
        """Convert name to string for backward compatibility with tests."""
        return str(value) if value is not None else None

    async def apply(
        self, transaction: Transaction, container: DependencyContainer, session: AsyncSession
    ) -> Transaction:
        """Simply returns the transaction unchanged."""
        return transaction
