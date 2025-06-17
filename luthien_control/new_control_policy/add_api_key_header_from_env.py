"""
Add an API key header, where the key is sourced from a configured environment variable.

This policy is used to add an API key to the request Authorization header.
The API key is read from an environment variable whose name is configured
when the policy is instantiated.
"""

import logging
import os
from typing import Optional, cast

from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction import Transaction
from luthien_control.new_control_policy.control_policy import ControlPolicy
from luthien_control.new_control_policy.exceptions import (
    ApiKeyNotFoundError,
    NoRequestError,
)
from luthien_control.new_control_policy.serialization import SerializableDict


class AddApiKeyHeaderFromEnvPolicy(ControlPolicy):
    """Adds an API key to the request Authorization header.
    The API key is read from an environment variable whose name is configured
    when the policy is instantiated.
    """

    def __init__(self, api_key_env_var_name: str, name: Optional[str] = None):
        """Initializes the policy.

        Args:
            api_key_env_var_name: The name of the environment variable that holds the API key.
            name: Optional name for this policy instance.
        """
        if not api_key_env_var_name:
            raise ValueError("api_key_env_var_name cannot be empty.")

        self.name = name or self.__class__.__name__
        self.api_key_env_var_name = api_key_env_var_name
        self.logger = logging.getLogger(__name__)

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
            # In the new model, we don't directly manipulate response - just raise the error
            raise ApiKeyNotFoundError(f"{error_message} ({self.name})")

        self.logger.info(f"Setting API key from env var '{self.api_key_env_var_name}' ({self.name}).")
        transaction.request.api_key = api_key

        return transaction

    def serialize(self) -> SerializableDict:
        """Serializes the policy's configuration."""
        return cast(
            SerializableDict,
            {
                "name": self.name,
                "api_key_env_var_name": self.api_key_env_var_name,
            },
        )

    @classmethod
    def from_serialized(cls, config: SerializableDict) -> "AddApiKeyHeaderFromEnvPolicy":
        """
        Constructs the policy from serialized configuration.

        Args:
            config: Dictionary expecting 'api_key_env_var_name' and optionally 'name'.

        Returns:
            An instance of AddApiKeyHeaderFromEnvPolicy.

        Raises:
            TypeError if 'name' is not a string.
            KeyError if 'api_key_env_var_name' is not in config.
        """
        instance_name = str(config.get("name"))
        api_key_env_var_name = config.get("api_key_env_var_name")

        if api_key_env_var_name is None:
            raise KeyError("Configuration for AddApiKeyHeaderFromEnvPolicy is missing 'api_key_env_var_name'.")
        if not isinstance(api_key_env_var_name, str):
            raise TypeError(f"API key environment variable name '{api_key_env_var_name}' is not a string.")

        return cls(
            api_key_env_var_name=api_key_env_var_name,
            name=instance_name,
        )
