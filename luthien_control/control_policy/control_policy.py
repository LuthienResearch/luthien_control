# Interfaces for the request processing framework.

import abc
from typing import TYPE_CHECKING, Any, Optional, Type, TypeVar

from luthien_control.control_policy.serialization import SerializableDict

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from luthien_control.core.dependency_container import DependencyContainer
    from luthien_control.core.transaction_context import TransactionContext

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
        self, context: "TransactionContext", container: "DependencyContainer", session: "AsyncSession"
    ) -> "TransactionContext":
        """
        Apply the policy to the transaction context using provided dependencies.

        Args:
            context: The current transaction context.
            container: The dependency injection container.
            session: The database session for the current request.

        Returns:
            The potentially modified transaction context.

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
    def from_serialized(cls: Type[PolicyT], config: SerializableDict, **kwargs: Any) -> PolicyT:
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
            NotImplementedError: If the concrete class's from_serialized is not implemented (should not happen for registered classes).
        """
        # Moved import inside the method to break circular dependency
        from luthien_control.control_policy.registry import POLICY_NAME_TO_CLASS

        policy_type_name = config.get("type")
        if not policy_type_name:
            raise ValueError("Policy configuration must include a 'type' field.")

        # Handle the case where the class calling this is already the concrete class
        # (e.g., SpecificPolicy.from_serialized() was called directly)
        # and cls.type matches policy_type_name (if cls has a 'type' attribute)
        # However, the primary design is for ControlPolicy.from_serialized to be the entry point.

        if cls is not ControlPolicy:
            # This means a subclass like BranchingPolicy.from_serialized() or MockPolicy.from_serialized()
            # is calling this method via super().from_serialized().
            # This path should ideally not be taken if the subclass itself is registered.
            # The expectation is that ControlPolicy.from_serialized is the main dispatcher.
            # If a subclass calls super().from_serialized(), and it *is* the target type,
            # it should handle its own deserialization.
            # For now, let's assume this means the subclass doesn't override from_serialized correctly
            # and is trying to use a generic dispatcher logic which is not intended here.
            # Or, it's a direct call like `MockPolicy.from_serialized(config)` where `config['type']` is `MockPolicy.type`.
            # The logic below handles finding the correct class via registry.
            pass

        target_policy_class = POLICY_NAME_TO_CLASS.get(policy_type_name)
        if not target_policy_class:
            raise ValueError(
                f"Unknown policy type '{policy_type_name}'. Ensure it is registered in POLICY_NAME_TO_CLASS."
            )

        # We expect the target_policy_class to have its own from_serialized method.
        # That method should be an async classmethod.
        return target_policy_class.from_serialized(config, **kwargs)
