"""
Add an API key header, where the key is sourced from a configured environment variable.

This policy is used to add an API key to the request Authorization header.
The API key is read from an environment variable whose name is configured
when the policy is instantiated.
"""

import os

from pydantic import Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import (
    ApiKeyNotFoundError,
    NoRequestError,
)
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction import Transaction


class AddApiKeyHeaderFromEnvPolicy(ControlPolicy):
    """Adds an API key to the request Authorization header from an environment variable.

    The API key is read from an environment variable whose name is configured
    when the policy is instantiated. This allows different API keys to be used
    based on deployment environment.
    """

    api_key_env_var_name: str = Field(...)

    @field_validator('api_key_env_var_name', mode='before')
    @classmethod
    def validate_api_key_env_var_name(cls, value):
        """Validate that api_key_env_var_name is a string, maintaining original strict behavior."""
        if value is None:
            raise ValueError("api_key_env_var_name cannot be None")
        if not isinstance(value, str):
            raise TypeError(f"API key environment variable name '{value}' is not a string.")
        return value


    async def apply(
        self,
        transaction: Transaction,
        container: DependencyContainer,
        session: AsyncSession,
    ) -> Transaction:
        """
        Sets the API key on the transaction's request.

        The API key is read from the environment variable specified by self.api_key_env_var_name.
        Requires DependencyContainer and AsyncSession for interface compliance, but they are not
        directly used in this policy's primary logic beyond what ControlPolicy might require.

        Raises:
            NoRequestError if the request is not found in the transaction.
            ApiKeyNotFoundError if the configured environment variable is not set or is empty.

        Args:
            transaction: The current transaction.
            container: The application dependency container (unused).
            session: An active SQLAlchemy AsyncSession (unused).

        Returns:
            The potentially modified transaction.
        """
        if transaction.request is None:
            raise NoRequestError("No request in transaction.")

        api_key = os.environ.get(self.api_key_env_var_name)

        if not api_key:
            error_message = (
                f"API key not found. Environment variable '{self.api_key_env_var_name}' is not set or is empty."
            )
            self.logger.error(f"{error_message} ({self.name})")
            raise ApiKeyNotFoundError(f"{error_message} ({self.name})")

        self.logger.info(f"Setting API key from env var '{self.api_key_env_var_name}' ({self.name}).")
        transaction.request.api_key = api_key

        return transaction
