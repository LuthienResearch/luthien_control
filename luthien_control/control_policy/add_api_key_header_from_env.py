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

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import (
    ApiKeyNotFoundError,
    NoRequestError,
)
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.tracked_context import TrackedContext

from .serialization import SerializableDict


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
        context: TrackedContext,
        container: DependencyContainer,
        session: AsyncSession,
    ) -> TrackedContext:
        """
        Adds the Authorization: Bearer <api_key> header to the context.request.

        The API key is read from the environment variable specified by self.api_key_env_var_name.
        Requires DependencyContainer and AsyncSession for interface compliance, but they are not
        directly used in this policy's primary logic beyond what ControlPolicy might require.

        Raises:
            NoRequestError if the request is not found in the context.
            ApiKeyNotFoundError if the configured environment variable is not set or is empty.

        Args:
            context: The current transaction context.
            container: The application dependency container (unused).
            session: An active SQLAlchemy AsyncSession (unused).

        Returns:
            The potentially modified transaction context.
        """
        # Set current policy for event tracking
        context.set_current_policy(self.name)

        if context.request is None:
            raise NoRequestError(f"[{context.transaction_id}] No request in context.")

        api_key = os.environ.get(self.api_key_env_var_name)

        if not api_key:
            error_message = (
                f"API key not found. Environment variable '{self.api_key_env_var_name}' is not set or is empty."
            )
            self.logger.error(f"[{context.transaction_id}] {error_message} ({self.name})")
            context.set_response(
                status_code=500,
                headers={"Content-Type": "application/json"},
                content=f'{{"detail": "Server configuration error: {error_message}"}}'.encode(),
            )
            raise ApiKeyNotFoundError(f"[{context.transaction_id}] {error_message} ({self.name})")

        self.logger.info(
            f"[{context.transaction_id}] Adding Authorization header from env var "
            f"'{self.api_key_env_var_name}' ({self.name})."
        )
        context.request.set_header("Authorization", f"Bearer {api_key}")

        # Clear current policy
        context.set_current_policy(None)
        return context

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
