"""Interfaces for the request processing framework."""

import abc
from typing import TYPE_CHECKING, Any, Type, TypeVar

from luthien_control.control_policy.serialization import SerializableDict

if TYPE_CHECKING:
    from luthien_control.core.transaction_context import TransactionContext

# Type variable for the policy classes
PolicyT = TypeVar("PolicyT", bound="ControlPolicy")


class ControlPolicy(abc.ABC):
    """Abstract Base Class defining the interface for a processing step."""

    name: str | None = None
    policy_class_path: str | None = None

    def __init__(self, **kwargs: Any) -> None:
        pass

    @abc.abstractmethod
    async def apply(self, context: "TransactionContext") -> "TransactionContext":
        """
        Apply the policy to the transaction context.

        Args:
            context: The current transaction context.

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
    @abc.abstractmethod
    def from_serialized(cls: Type[PolicyT], config: SerializableDict, **kwargs) -> PolicyT:
        """
        Construct a policy from a serialized configuration and optional dependencies.

        Args:
            config: The policy-specific configuration dictionary.
            **kwargs: Additional dependencies needed for instantiation.

        Returns:
            An instance of the policy class.
        """
        raise NotImplementedError
