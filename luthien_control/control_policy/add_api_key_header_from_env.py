# Add an API key header, where the key is sourced from a configured environment variable.


import logging
import os
from typing import Optional, cast

from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import (
    ApiKeyNotFoundError,
    NoRequestError,
)
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction_context import TransactionContext

from .serialization import SerializableDict


class AddApiKeyHeaderFromEnvPolicy(ControlPolicy):
    """Adds an API key to the request Authorization header.

    The API key is read from an environment variable whose name is configured
    when the policy is instantiated.

    Attributes:
        name (str): The name of this policy instance.
        api_key_env_var_name (str): The name of the environment variable
            that holds the API key.
        logger (logging.Logger): The logger instance for this policy.
    """

    def __init__(self, api_key_env_var_name: str, name: Optional[str] = None):
        """Initializes the policy.

        Args:
            api_key_env_var_name: The name of the environment variable that
                holds the API key.
            name: Optional name for this policy instance.

        Raises:
            ValueError: If `api_key_env_var_name` is empty.
        """
        if not api_key_env_var_name:
            raise ValueError("api_key_env_var_name cannot be empty.")

        self.name = name or self.__class__.__name__
        self.api_key_env_var_name = api_key_env_var_name
        self.logger = logging.getLogger(__name__)

    async def apply(
        self,
        context: TransactionContext,
        container: DependencyContainer,
        session: AsyncSession,
    ) -> TransactionContext:
        """
        Adds the Authorization: Bearer <api_key> header to the context.request.

        The API key is read from the environment variable specified by self.api_key_env_var_name.
        Requires DependencyContainer and AsyncSession for interface compliance, but they are not
        directly used in this policy's primary logic beyond what ControlPolicy might require.

        Args:
            context: The current transaction context.
            container: The application dependency container (unused).
            session: An active SQLAlchemy AsyncSession (unused).

        Returns:
            The potentially modified transaction context.

        Raises:
            NoRequestError if the request is not found in the context.
            ApiKeyNotFoundError if the configured environment variable is not set or is empty.
        """
        if context.request is None:
            raise NoRequestError(f"[{context.transaction_id}] No request in context.")

        api_key = os.environ.get(self.api_key_env_var_name)

        if not api_key:
            error_message = (
                f"API key not found. Environment variable '{self.api_key_env_var_name}' is not set or is empty."
            )
            self.logger.error(f"[{context.transaction_id}] {error_message} ({self.name})")
            context.response = JSONResponse(
                status_code=500,
                content={"detail": f"Server configuration error: {error_message}"},
            )
            raise ApiKeyNotFoundError(f"[{context.transaction_id}] {error_message} ({self.name})")

        self.logger.info(
            f"[{context.transaction_id}] Adding Authorization header from env var "
            f"'{self.api_key_env_var_name}' ({self.name})."
        )
        context.request.headers["Authorization"] = f"Bearer {api_key}"
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
    async def from_serialized(cls, config: SerializableDict) -> "AddApiKeyHeaderFromEnvPolicy":
        """
        Constructs the policy from serialized configuration.

        Args:
            config: Dictionary expecting 'api_key_env_var_name' and optionally 'name'.

        Returns:
            An instance of AddApiKeyHeaderFromEnvPolicy.

        Raises:
            KeyError if 'api_key_env_var_name' is not in config.
        """
        instance_name = config.get("name")
        api_key_env_var_name = config.get("api_key_env_var_name")

        if api_key_env_var_name is None:  # Ensure it's present, even if it could be an empty string (handled by init)
            raise KeyError("Configuration for AddApiKeyHeaderFromEnvPolicy is missing 'api_key_env_var_name'.")

        return cls(
            name=instance_name,
            api_key_env_var_name=str(api_key_env_var_name),  # Ensure it's a string
        )
