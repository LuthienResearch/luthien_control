"""Control processor for applying request-side policies."""

from luthien_control.control_processors.interface import ControlProcessor
from luthien_control.core.context import TransactionContext

# Import the actual PolicyLoader
from luthien_control.policies.loader import PolicyLoader


class PolicyViolationError(Exception):
    pass


class ApplyRequestPolicyProcessor(ControlProcessor):
    """Applies request-side policies loaded via a PolicyLoader."""

    def __init__(self, policy_loader: PolicyLoader):
        """Initializes the processor with a policy loader instance."""
        self.policy_loader = policy_loader

    async def process(self, context: TransactionContext) -> TransactionContext:
        """
        Retrieves request policies from the policy loader and applies them sequentially.

        Potential modifications to context:
            - context.data: Policy decisions or modifications might be stored.
            - Raises PolicyViolationError: If a policy explicitly denies the request.

        Args:
            context: The current transaction context.

        Returns:
            The potentially modified transaction context.
        """
        print(f"[{context.transaction_id}] Applying request policies...")

        # Get loaded policies from the loader
        request_policies = self.policy_loader.get_request_policies()

        if not request_policies:
            print(f"[{context.transaction_id}] No request policies configured/loaded.")
            return context

        for policy in request_policies:
            try:
                print(f"[{context.transaction_id}] Applying request policy: {policy.__class__.__name__}")
                context = await policy.apply_request(context)
            except PolicyViolationError as e:
                print(f"[{context.transaction_id}] Policy violation by {policy.__class__.__name__}: {e}")
                raise  # Re-raise to halt processing
            except Exception as e:
                # Catch potential errors within policy apply_request methods
                print(f"[{context.transaction_id}] ERROR applying policy {policy.__class__.__name__}: {e}")
                # Depending on desired behavior, might want to raise a specific ProcessorError
                # For now, re-raise the original exception
                raise

        print(f"[{context.transaction_id}] Request policies applied successfully.")
        return context

    # Removed the placeholder _load_request_policies method
