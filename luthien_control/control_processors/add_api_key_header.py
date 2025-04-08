"""Control processor for adding the API key header to requests."""


from luthien_control.config.settings import Settings
from luthien_control.control_processors.interface import ControlProcessor
from luthien_control.core.context import TransactionContext


class AddApiKeyHeaderProcessor(ControlProcessor):
    """Adds the configured API key (e.g., OpenAI) to the request Authorization header."""

    def __init__(self, settings: Settings):
        """Initializes the processor with settings."""
        self.settings = settings

    async def process(self, context: TransactionContext) -> TransactionContext:
        """
        Adds the Authorization: Bearer <api_key> header to the context.request.

        Reads API key from settings.
        No-op if context.request is None or API key is not configured.

        Args:
            context: The current transaction context.

        Returns:
            The potentially modified transaction context.
        """
        if context.request is None:
            print(f"[{context.transaction_id}] Skipping API key addition: No request in context.")
            return context

        api_key = self.settings.get_openai_api_key()

        if not api_key:
            print(f"[{context.transaction_id}] Skipping API key addition: Key not configured.")
            return context

        print(f"[{context.transaction_id}] Adding Authorization header.")
        # httpx.Headers are mutable, so we can modify in place
        context.request.headers["Authorization"] = f"Bearer {api_key}"

        return context
