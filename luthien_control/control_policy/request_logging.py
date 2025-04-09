"""Control Policy for logging request details."""

import logging

from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.core.context import TransactionContext


class RequestLoggingPolicy(ControlPolicy):
    """Logs essential details about the incoming request."""

    def __init__(self):
        # Policies are typically instantiated once, so get the logger here
        self.logger = logging.getLogger(__name__)

    async def apply(self, context: TransactionContext) -> TransactionContext:
        """Logs request details from the context and returns the context unmodified."""
        # TODO: Implement logging logic
        # 1. Check if context.request exists.
        # 2. Extract method, url, headers (maybe selectively?), transaction_id.
        # 3. Log this information using self.logger.
        # 4. Return context unmodified.
        raise NotImplementedError("RequestLoggingPolicy is not implemented.")
