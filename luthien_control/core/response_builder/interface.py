import logging
from typing import Optional, Protocol, runtime_checkable

from fastapi import Response
from luthien_control.control_policy.exceptions import ControlPolicyError
from luthien_control.core.context import TransactionContext


@runtime_checkable
class ResponseBuilder(Protocol):
    """Protocol defining the interface for building the final client response."""

    def __init__(self):
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)

    def build_response(self, context: TransactionContext, exception: Optional[ControlPolicyError] = None) -> Response:
        """
        Build the final FastAPI response based on the transaction context.

        Args:
            context: The final transaction context after all policies have run.
            exception: An optional exception that occurred during policy execution.

        Returns:
            A FastAPI Response object to be sent to the client.
        """
        raise NotImplementedError(f"Builder {self.__class__.__name__} must implement the build_response method.")
