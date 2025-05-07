"""Control Policy for adding a header to requests from an environment variable."""

import logging
import os
from typing import Optional, cast

from fastapi.responses import JSONResponse
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import NoRequestError
from luthien_control.core.transaction_context import TransactionContext
from luthien_control.core.dependency_container import DependencyContainer
from sqlalchemy.ext.asyncio import AsyncSession

from .serialization import SerializableDict


class AddHeaderFromEnvPolicy(ControlPolicy):
    """Adds a specified header to the request, taking its value from an environment variable."""

    def __init__(self, header_name: str, env_var_name: str, name: Optional[str] = None):
        """
        Initializes the policy.

        Args:
            header_name: The name of the header to add (e.g., "Authorization").
            env_var_name: The name of the environment variable to source the header value from.
            name: Optional name for the policy instance.
        """
        if not header_name:
            raise ValueError("header_name cannot be empty.")
        if not env_var_name:
            raise ValueError("env_var_name cannot be empty.")

        self.name = name or self.__class__.__name__
        self.header_name = header_name
        self.env_var_name = env_var_name
        self.logger = logging.getLogger(__name__)

    async def apply(
        self,
        context: TransactionContext,
        container: DependencyContainer,
        session: AsyncSession,
    ) -> TransactionContext:
        """
        Adds the specified header to context.request.headers using a value from an environment variable.

        Requires the DependencyContainer and AsyncSession in signature for interface compliance,
        but they are not directly used in this policy's logic beyond basic context checks.

        Raises:
            NoRequestError if the request is not found in the context.
            ValueError if the specified environment variable is not set.

        Args:
            context: The current transaction context.
            container: The application dependency container (unused).
            session: An active SQLAlchemy AsyncSession (unused).

        Returns:
            The potentially modified transaction context.
        """
        if context.request is None:
            raise NoRequestError(f"[{context.transaction_id}] No request in context for {self.name}.")

        header_value = os.environ.get(self.env_var_name)

        if header_value is None:
            error_msg = f"Environment variable '{self.env_var_name}' not set for policy {self.name}."
            self.logger.error(f"[{context.transaction_id}] {error_msg}")
            context.response = JSONResponse(
                status_code=500,
                content={
                    "detail": f"Server configuration error: Required information not found for header '{self.header_name}'."
                },
            )
            raise ValueError(f"[{context.transaction_id}] {error_msg}")

        self.logger.info(
            f"[{context.transaction_id}] Adding header '{self.header_name}' "
            f"from environment variable '{self.env_var_name}' ({self.name})."
        )
        context.request.headers[self.header_name] = header_value
        return context

    def serialize(self) -> SerializableDict:
        """Serializes the policy's configuration."""
        return cast(
            SerializableDict,
            {
                "name": self.name,
                "header_name": self.header_name,
                "env_var_name": self.env_var_name,
            },
        )

    @classmethod
    async def from_serialized(cls, config: SerializableDict) -> "AddHeaderFromEnvPolicy":
        """
        Constructs the policy from serialized configuration.

        Args:
            config: Dictionary containing 'header_name', 'env_var_name', and optionally 'name'.

        Returns:
            An instance of AddHeaderFromEnvPolicy.

        Raises:
            KeyError: if 'header_name' or 'env_var_name' are missing from config.
        """
        instance_name = config.get("name")
        header_name = config["header_name"]  # Raises KeyError if missing, which is desired.
        env_var_name = config["env_var_name"]  # Raises KeyError if missing.
        return cls(name=instance_name, header_name=header_name, env_var_name=env_var_name)
