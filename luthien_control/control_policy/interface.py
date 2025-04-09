"""Interfaces for the request processing framework."""

from typing import Protocol, runtime_checkable

from luthien_control.core.context import TransactionContext


@runtime_checkable
class ControlPolicy(Protocol):
    """Protocol defining the interface for a single processing step."""

    async def apply(self, context: TransactionContext) -> TransactionContext:
        """
        Apply the policy to the transaction context.

        Args:
            context: The current transaction context.

        Returns:
            The potentially modified transaction context.

        Raises:
            Exception: Processors may raise exceptions to halt the processing flow.
        """
        raise NotImplementedError(f"Policy {self.__class__.__name__} must implement the apply method.")
