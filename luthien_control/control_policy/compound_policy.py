"""Compound Policy that applies a sequence of other policies."""

import logging
from typing import Iterable, Optional, Sequence, cast

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import PolicyLoadError
from luthien_control.control_policy.loader import load_policy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.transaction_context import TransactionContext

logger = logging.getLogger(__name__)


class CompoundPolicy(ControlPolicy):
    """
    A Control Policy that applies an ordered sequence of other policies.

    Policies are applied sequentially. If any policy raises an exception,
    the execution stops, and the exception propagates.
    """

    REQUIRED_DEPENDENCIES = ["http_client", "settings"]

    def __init__(self, policies: Sequence[ControlPolicy], name: Optional[str] = None):
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
        self.name = name or self.__class__.__name__

    async def apply(self, context: "TransactionContext") -> "TransactionContext":
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
            member_policy_name = getattr(policy, "name", policy.__class__.__name__)  # Get policy name if available
            self.logger.debug(
                f"[{current_context.transaction_id}] Applying policy {i + 1}/{len(self.policies)} "
                f"in {self.name}: {member_policy_name}"
            )
            try:
                current_context = await policy.apply(current_context)
            except Exception as e:
                self.logger.error(
                    f"[{current_context.transaction_id}] Error applying policy {member_policy_name} "
                    f"within {self.name}: {e}",
                    exc_info=True,
                )
                raise  # Re-raise the exception to halt processing
        self.logger.debug(f"[{context.transaction_id}] Exiting CompoundPolicy: {self.name}")
        return current_context

    def __repr__(self) -> str:
        """Provides a developer-friendly representation."""
        # Get the name of each policy, using getattr as fallback like in apply
        policy_reprs = [f"{p.name} <{p.__class__.__name__}>" for p in self.policies]
        policy_list_str = ", ".join(policy_reprs)
        return f"<{self.name}(policies=[{policy_list_str}])>"

    def serialize(self) -> SerializableDict:
        # Import from registry here to avoid circular import
        from .registry import POLICY_CLASS_TO_NAME

        member_configs = []
        for p in self.policies:
            try:
                policy_type = POLICY_CLASS_TO_NAME.get(type(p))
            except ImportError:  # Should not happen if loader exists
                raise PolicyLoadError(
                    f"Could not determine policy type for {type(p)} during serialization in {self.name} "
                    "(Not in POLICY_CLASS_TO_NAME)"
                )

            member_configs.append(
                {
                    "type": policy_type,
                    "config": p.serialize(),
                }
            )
        # Return a dictionary literal conforming to SerializableDict
        return cast(SerializableDict, {"policies": member_configs})

    @classmethod
    async def from_serialized(cls, config: SerializableDict, **kwargs) -> "CompoundPolicy":
        """
        Constructs a CompoundPolicy from serialized data, loading member policies.

        Args:
            config: The serialized configuration dictionary. Expects a 'policies' key
                    containing a list of dictionaries, each with 'name' and 'config'.
            **kwargs: Dependencies (e.g., api_key_lookup) passed down to members.

        Returns:
            An instance of CompoundPolicy.

        Raises:
            PolicyLoadError: If 'policies' key is missing, not a list, or if loading
                             a member policy fails.
        """
        try:
            member_policy_data_list = config["policies"]
        except KeyError:
            raise PolicyLoadError("CompoundPolicy config missing 'policies' list.")
        if not isinstance(member_policy_data_list, Iterable):
            raise PolicyLoadError("CompoundPolicy 'policies' must be an iterable.")

        instantiated_policies = []

        for i, member_data in enumerate(member_policy_data_list):
            if not isinstance(member_data, dict):
                raise PolicyLoadError(f"Item at index {i} in CompoundPolicy 'policies' is not a dictionary.")
            try:
                # Call the simple loader, passing all available dependencies down
                member_policy = await load_policy(member_data, **kwargs)
                instantiated_policies.append(member_policy)
            except PolicyLoadError as e:
                # Add context about which member failed
                raise PolicyLoadError(
                    f"Failed to load member policy at index {i} "
                    f"(name: {member_data.get('name', 'unknown')}) "
                    f"within CompoundPolicy: {e}"
                ) from e
            except Exception as e:
                raise PolicyLoadError(
                    f"Unexpected error loading member policy at index {i} "
                    f"(name: {member_data.get('name', 'unknown')}) "
                    f"within CompoundPolicy: {e}"
                ) from e

        # Extract the name for the CompoundPolicy itself from the config, if provided
        compound_policy_name = config.get("name", "CompoundPolicy")  # Default name if not in config

        return cls(policies=instantiated_policies, name=compound_policy_name)
