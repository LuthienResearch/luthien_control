""" ""Compound Policy that applies a sequence of other policies."""

import logging
from typing import Any, Sequence

from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.core.context import TransactionContext

logger = logging.getLogger(__name__)


class CompoundPolicy(ControlPolicy):
    """
    A Control Policy that applies an ordered sequence of other policies.

    Policies are applied sequentially. If any policy raises an exception,
    the execution stops, and the exception propagates.
    """

    def __init__(self, policies: Sequence[ControlPolicy], name: str = "CompoundPolicy"):
        """
        Initializes the CompoundPolicy.

        Args:
            policies: An ordered sequence of ControlPolicy instances to apply.
            name: An optional name for logging/identification purposes.
        """
        if not policies:
            logger.warning(f"Initializing CompoundPolicy '{name}' with an empty policy list.")
        self.policies = policies
        self.logger = logger

    async def apply(self, context: TransactionContext) -> TransactionContext:
        """
        Applies the contained policies sequentially to the context.

        Args:
            context: The current transaction context.

        Returns:
            The transaction context after all contained policies have been applied.

        Raises:
            Exception: Propagates any exception raised by a contained policy.
        """
        self.logger.debug(f"[{context.transaction_id}] Entering CompoundPolicy: {self.name}")
        current_context = context
        for i, policy in enumerate(self.policies):
            policy_name = getattr(policy, "name", policy.__class__.__name__)  # Get policy name if available
            self.logger.debug(
                f"[{current_context.transaction_id}] Applying policy {i + 1}/{len(self.policies)} "
                f"in {self.name}: {policy_name}"
            )
            current_context = await policy.apply(current_context)
            # If a policy set a response, stop processing (consistent with ControlPolicyError handling)
            if current_context.response is not None:
                self.logger.info(
                    f"[{current_context.transaction_id}] Policy {policy_name} in {self.name} "
                    f"set a response. Halting CompoundPolicy execution."
                )
                break
        self.logger.debug(f"[{context.transaction_id}] Exiting CompoundPolicy: {self.name}")
        return current_context

    def __repr__(self) -> str:
        policy_names = [getattr(p, "name", p.__class__.__name__) for p in self.policies]
        return f"<{self.name}(policies={policy_names})>"

    def serialize_config(self) -> dict[str, Any]:
        """Serializes the CompoundPolicy configuration by listing member names."""
        member_names = []
        for policy in self.policies:
            if policy.name is None:
                # This should ideally not happen if policies are loaded correctly
                raise ValueError(
                    f"Cannot serialize CompoundPolicy '{self.name}': member policy "
                    f"{policy.__class__.__name__} has no name set."
                )
            member_names.append(policy.name)

        return {"member_policy_names": member_names}
