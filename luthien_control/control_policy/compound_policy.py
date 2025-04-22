""" ""Compound Policy that applies a sequence of other policies."""

import logging
from typing import Any, Sequence

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.core.transaction_context import TransactionContext

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
        self.name = name

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
        self.logger.debug(f"[{context.transaction_id}] Exiting CompoundPolicy: {self.name}")
        return current_context

    def __repr__(self) -> str:
        policy_names = [getattr(p, "name", p.__class__.__name__) for p in self.policies]
        return f"<{self.name}(policies={policy_names})>"

    def serialize_config(self) -> dict[str, Any]:
        """Serializes the CompoundPolicy configuration including member configurations."""
        member_policy_configs = []
        for policy in self.policies:
            # Ensure member policy has a name before proceeding
            if policy.name is None:
                raise ValueError(
                    f"Cannot serialize CompoundPolicy '{self.name}': member policy "
                    f"{policy.__class__.__name__} has no name set."
                )

            try:
                member_config = policy.serialize_config()
                # Ensure the member config includes its type for deserialization
                if "__policy_type__" not in member_config:
                    # Add type if the member policy didn't already add it (best practice)
                    member_config["__policy_type__"] = policy.__class__.__name__
                # Store the policy name within its config as well, if available
                if policy.name:
                    member_config["name"] = policy.name
                member_policy_configs.append(member_config)
            except NotImplementedError:
                # Handle policies that don't implement serialization (if any)
                policy_name = getattr(policy, "name", policy.__class__.__name__)
                self.logger.error(
                    f"[{self.name}] Member policy '{policy_name}' does not implement "
                    f"serialize_config(). Cannot fully serialize CompoundPolicy."
                )
                raise NotImplementedError(
                    f"Member policy '{policy_name}' in CompoundPolicy '{self.name}' does not support serialization."
                )
            except Exception as e:
                policy_name = getattr(policy, "name", policy.__class__.__name__)
                self.logger.error(f"[{self.name}] Error serializing member policy '{policy_name}': {e}", exc_info=True)
                raise RuntimeError(f"Failed to serialize member policy '{policy_name}'.") from e

        # Prepare the final dictionary
        serialized_data = {
            "__policy_type__": self.__class__.__name__,
            "name": self.name,
            "member_policy_configs": member_policy_configs,  # Embed full configs
        }

        # Add the class path if it exists on the instance
        if hasattr(self, "policy_class_path") and self.policy_class_path:
            serialized_data["policy_class_path"] = self.policy_class_path
        else:
            # This indicates the instance wasn't loaded correctly via load_policy_instance
            # or the attribute wasn't added to the interface/class.
            self.logger.warning(
                f"Cannot find 'policy_class_path' attribute on CompoundPolicy '{self.name}' instance. "
                f"Serialization might be incomplete for direct reloading."
            )

        return serialized_data
