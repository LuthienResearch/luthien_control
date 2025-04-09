"""Core control policy implementations."""

import httpx
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.core.context import TransactionContext


class SendBackendRequestPolicy(ControlPolicy):
    """Policy responsible for sending the request to the backend and storing the response."""

    def __init__(self, http_client: httpx.AsyncClient):
        self.http_client = http_client

    async def apply(self, context: TransactionContext) -> TransactionContext:
        """Sends the request in context.request to the backend via http_client."""
        if not context.request:
            # Raise an error if the request is missing, as we cannot proceed.
            # Consider adding specific logging here if needed.
            raise ValueError("Cannot send request: context.request is None")

        try:
            response = await self.http_client.send(context.request)
            # TODO: Consider adding response streaming support check? httpx handles it mostly.
            # Store the response in the context
            context.response = response
        except Exception as e:
            # Log the exception? Currently, just re-raise to halt processing.
            # Ensure context.response remains None or is cleared on error.
            context.response = None
            raise e

        return context
