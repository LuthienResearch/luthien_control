"""Interfaces for the request processing framework."""

import abc
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from luthien_control.core.transaction_context import TransactionContext


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
    def serialize_config(self) -> dict[str, Any]:
        """
        Serialize the policy's instance-specific configuration needed for reloading.

        Returns:
            A dictionary containing configuration parameters. Excludes dependencies
            like settings, http_client, etc., that are injected during loading.
            Includes parameters needed for composite policies (like member names).
        """
        raise NotImplementedError
