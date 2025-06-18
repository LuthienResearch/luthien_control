# Interfaces for the request processing framework.

import abc
import logging
from typing import Any, Optional, Type, TypeVar, cast

from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction import Transaction
from luthien_control.new_control_policy.serialization import SerializableDict

# Type variable for the policy classes
PolicyT = TypeVar("PolicyT", bound="ControlPolicy")


class ControlPolicy(abc.ABC):
    """Abstract Base Class defining the interface for a processing step.

    Attributes:
        name (Optional[str]): An optional name for the policy instance.
            Subclasses are expected to set this, often in their `__init__` method.
            It's used for logging and identification purposes.
    """

    name: Optional[str] = None

    @classmethod
    def get_policy_type_name(cls) -> str:
        """Get the canonical policy type name for serialization.

        By default, this looks up the class in the registry to get its registered name.
        Subclasses can override this if they need custom behavior.

        Returns:
            The policy type name used in serialization.
        """
        # Import here to avoid circular imports
        from luthien_control.new_control_policy.registry import POLICY_CLASS_TO_NAME

        policy_type = POLICY_CLASS_TO_NAME.get(cls)
        if policy_type is None:
            raise ValueError(f"{cls.__name__} is not registered in POLICY_CLASS_TO_NAME registry")
        return policy_type

    def __init__(self, **kwargs: Any) -> None:
        """Initializes the ControlPolicy.

        This is an abstract base class, and this constructor typically handles
        common initialization or can be overridden by subclasses.

        Args:
            **kwargs: Arbitrary keyword arguments that subclasses might use.
        """
        self.logger = logging.getLogger(__name__)

    @abc.abstractmethod
    async def apply(
        self,
        transaction: "Transaction",
        container: "DependencyContainer",
        session: "AsyncSession",
    ) -> "Transaction":
        """
        Apply the policy to the transaction using provided dependencies.

        Args:
            transaction: The current transaction.
            container: The dependency injection container.
            session: The database session for the current request.

        Returns:
            The potentially modified transaction.

        Raises:
            Exception: Processors may raise exceptions to halt the processing flow.
        """
        raise NotImplementedError

    def serialize(self) -> SerializableDict:
        """
        Serialize the policy's instance-specific configuration needed for reloading.

        This default implementation creates a SerializableDict with the policy type
        and delegates to get_policy_config() for policy-specific configuration.

        Returns:
            A serializable dictionary containing the policy type and configuration.
        """
        config = self.get_policy_config()
        config["type"] = self.get_policy_type_name()
        return config

    @abc.abstractmethod
    def get_policy_config(self) -> SerializableDict:
        """
        Get the policy-specific configuration for serialization.

        Subclasses should implement this to return their configuration without
        the "type" field, which is handled by the base serialize() method.

        Returns:
            A dictionary containing the policy's configuration.
        """
        raise NotImplementedError

    # construct from serialization
    @classmethod
    def from_serialized(cls: Type[PolicyT], config: SerializableDict) -> PolicyT:
        """
        Construct a policy from a serialized configuration and optional dependencies.

        This method acts as a dispatcher. It looks up the concrete policy class
        based on the 'type' field in the config and delegates to its from_serialized method.

        Args:
            config: The policy-specific configuration dictionary. It must contain a 'type' key
                    that maps to a registered policy type.
            **kwargs: Additional dependencies needed for instantiation, passed to the
                      concrete policy's from_serialized method.

        Returns:
            An instance of the concrete policy class.

        Raises:
            ValueError: If the 'type' key is missing in config or the type is not registered.
        """
        # Import inside the method to break circular dependency
        from luthien_control.new_control_policy.registry import POLICY_NAME_TO_CLASS

        policy_type_name_val = config.get("type")
        if not isinstance(policy_type_name_val, str):
            raise ValueError(
                f"Policy configuration must include a 'type' field as a string. "
                f"Got: {policy_type_name_val!r} (type: {type(policy_type_name_val).__name__})"
            )

        target_policy_class = POLICY_NAME_TO_CLASS.get(policy_type_name_val)
        if not target_policy_class:
            raise ValueError(
                f"Unknown policy type '{policy_type_name_val}'. Ensure it is registered in POLICY_NAME_TO_CLASS."
            )

        return cast(PolicyT, target_policy_class.from_serialized(config))
