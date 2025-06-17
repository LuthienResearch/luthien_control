# Interfaces for the request processing framework.

import abc
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

    def __init__(self, **kwargs: Any) -> None:
        """Initializes the ControlPolicy.

        This is an abstract base class, and this constructor typically handles
        common initialization or can be overridden by subclasses.

        Args:
            **kwargs: Arbitrary keyword arguments that subclasses might use.
        """
        pass

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

    @abc.abstractmethod
    def serialize(self) -> SerializableDict:
        """
        Serialize the policy's instance-specific configuration needed for reloading.

        Returns:
            A serializable dictionary containing configuration parameters.
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
