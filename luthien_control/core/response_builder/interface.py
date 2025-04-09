import logging
from typing import Protocol

from fastapi import Response
from luthien_control.core.context import TransactionContext


class ResponseBuilder(Protocol):
    """Protocol defining the interface for building the final client response."""

    def __init__(self):
        self.logger: logging.Logger = logging.getLogger(self.__class__.__name__)

    def build_response(self, context: TransactionContext) -> Response:
        """
        Build the final FastAPI response based on the transaction context.

        Args:
            context: The final transaction context after all policies have run.

        Returns:
            A FastAPI Response object to be sent to the client.
        """
        raise NotImplementedError(f"Builder {self.__class__.__name__} must implement the build_response method.")
