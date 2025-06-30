from typing import Optional

from pydantic import Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction import Transaction


class SetBackendPolicy(ControlPolicy):
    """A policy that sets the backend URL for the transaction."""

    backend_url: Optional[str] = Field(default=None)

    @field_validator('name', mode='before')
    @classmethod
    def validate_name(cls, value):
        """Convert non-string names to None for backward compatibility."""
        if value is None or isinstance(value, str):
            return value
        return None

    @field_validator('backend_url', mode='before')
    @classmethod
    def validate_backend_url(cls, value):
        """Convert non-string backend_url to None for backward compatibility."""
        if value is None or isinstance(value, str):
            return value
        return None

    async def apply(
        self, transaction: Transaction, container: DependencyContainer, session: AsyncSession
    ) -> Transaction:
        if self.backend_url is not None:
            transaction.request.api_endpoint = self.backend_url
        return transaction

    def _get_policy_specific_config(self) -> SerializableDict:
        """Return policy-specific configuration for backward compatibility with tests."""
        return SerializableDict(
            backend_url=self.backend_url,
        )
