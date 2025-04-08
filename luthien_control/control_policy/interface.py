"""Interfaces for the request processing framework."""

from typing import Protocol

# Import TransactionContext from its new location
from luthien_control.core.context import TransactionContext

# The TransactionContext class definition has been moved to luthien_control.core.context


class ControlProcessor(Protocol):
    """Protocol defining the interface for a single processing step."""

    async def process(self, context: TransactionContext) -> TransactionContext:
        """
        Processes the transaction context.

        Args:
            context: The current transaction context.

        Returns:
            The potentially modified transaction context.

        Raises:
            Exception: Processors may raise exceptions to halt the processing flow.
        """
        ...
