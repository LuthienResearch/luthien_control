# Serial Policy that applies a sequence of other policies.

import logging
from typing import Iterable, Optional, Sequence, cast

from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import PolicyLoadError
from luthien_control.control_policy.loader import load_policy
from luthien_control.control_policy.serialization import SerializableDict, SerializedPolicy
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction_context import TransactionContext

logger = logging.getLogger(__name__)


class SerialPolicy(ControlPolicy):
    """
    A Control Policy that applies an ordered sequence of other policies.

    Policies are applied sequentially. If any policy raises an exception,
    the execution stops, and the exception propagates.

    Attributes:
        policies (Sequence[ControlPolicy]): The ordered sequence of ControlPolicy
            instances that this policy will apply.
        logger (logging.Logger): The logger instance for this policy.
        name (str): The name of this policy instance, used for logging and
            identification.
    """

    def __init__(self, policies: Sequence[ControlPolicy], name: Optional[str] = None):
        """
        Initializes the SerialPolicy.

        Args:
            policies: An ordered sequence of ControlPolicy instances to apply.
            name: An optional name for logging/identification purposes.
        """
        if not policies:
            logger.warning(f"Initializing SerialPolicy '{name}' with an empty policy list.")
        self.policies = policies
        self.logger = logger
        self.name = name or self.__class__.__name__

    async def apply(
        self,
        context: "TransactionContext",
        container: DependencyContainer,
        session: AsyncSession,
    ) -> "TransactionContext":
        """
        Applies the contained policies sequentially to the context.
        Requires the DependencyContainer and an active SQLAlchemy AsyncSession.

        Args:
            context: The current transaction context.
            container: The application dependency container.
            session: An active SQLAlchemy AsyncSession, passed to member policies.

        Returns:
            The transaction context after all contained policies have been applied.

        Raises:
            Exception: Propagates any exception raised by a contained policy.
        """
        self.logger.debug(f"[{context.transaction_id}] Entering SerialPolicy: {self.name}")
        current_context = context
        for i, policy in enumerate(self.policies):
            member_policy_name = getattr(policy, "name", policy.__class__.__name__)  # Get policy name if available
            self.logger.info(
                f"[{current_context.transaction_id}] Applying policy {i + 1}/{len(self.policies)} "
                f"in {self.name}: {member_policy_name}"
            )
            try:
                current_context = await policy.apply(current_context, container=container, session=session)
            except Exception as e:
                self.logger.error(
                    f"[{current_context.transaction_id}] Error applying policy {member_policy_name} "
                    f"within {self.name}: {e}",
                    exc_info=True,
                )
                raise  # Re-raise the exception to halt processing
        self.logger.debug(f"[{context.transaction_id}] Exiting SerialPolicy: {self.name}")
        return current_context

    def __repr__(self) -> str:
        """Provides a developer-friendly representation."""
        # Get the name of each policy, using getattr as fallback like in apply
        policy_reprs = [f"{p.name} <{p.__class__.__name__}>" for p in self.policies]
        policy_list_str = ", ".join(policy_reprs)
        return f"<{self.name}(policies=[{policy_list_str}])>"

    def serialize(self) -> SerializableDict:
        """Serializes the SerialPolicy into a dictionary.

        This method converts the policy and its contained member policies
        into a serializable dictionary format. It uses the POLICY_CLASS_TO_NAME
        mapping to determine the 'type' string for each member policy.

        Returns:
            SerializableDict: A dictionary representation of the policy,
                              suitable for JSON serialization or persistence.
                              The dictionary has a "policies" key, which is a list
                              of serialized member policies. Each member policy dict
                              contains "type" and "config" keys.

        Raises:
            PolicyLoadError: If the type of a member policy cannot be determined
                             from POLICY_CLASS_TO_NAME.
        """
        # Import from registry here to avoid circular import
        from .registry import POLICY_CLASS_TO_NAME

        member_configs = []
        for p in self.policies:
            try:
                policy_type = POLICY_CLASS_TO_NAME[type(p)]
            except KeyError:
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
        return cast(SerializableDict, {"policies": member_configs})

    @classmethod
    def from_serialized(cls, config: SerializableDict) -> "SerialPolicy":
        """
        Constructs a SerialPolicy from serialized data, loading member policies.

        Args:
            config: The serialized configuration dictionary. Expects a 'policies' key
                    containing a list of dictionaries, each with 'type' and 'config'.

        Returns:
            An instance of SerialPolicy.

        Raises:
            PolicyLoadError: If 'policies' key is missing, not a list, or if loading
                             a member policy fails.
        """
        member_policy_data_list_val = config.get("policies")

        if member_policy_data_list_val is None:
            raise PolicyLoadError("SerialPolicy config missing 'policies' list (key not found).")
        if not isinstance(member_policy_data_list_val, Iterable):
            raise PolicyLoadError(
                f"SerialPolicy 'policies' must be an iterable. Got {type(member_policy_data_list_val)}"
            )

        instantiated_policies = []

        for i, member_data in enumerate(member_policy_data_list_val):
            if not isinstance(member_data, dict):
                raise PolicyLoadError(
                    f"Item at index {i} in SerialPolicy 'policies' is not a dictionary. Got {type(member_data)}"
                )

            # Extract 'type' and 'config' for SerializedPolicy construction
            member_policy_type = member_data.get("type")
            member_policy_config = member_data.get("config")

            if not isinstance(member_policy_type, str):
                raise PolicyLoadError(
                    f"Member policy at index {i} in SerialPolicy 'policies' is missing 'type' "
                    f"or it's not a string. Got {type(member_policy_type)}"
                )
            if not isinstance(member_policy_config, dict):
                raise PolicyLoadError(
                    f"Member policy at index {i} in SerialPolicy 'policies' is missing 'config' "
                    f"or it's not a dictionary. Got {type(member_policy_config)}"
                )

            try:
                # Construct SerializedPolicy dataclass instance
                serialized_member_policy = SerializedPolicy(type=member_policy_type, config=member_policy_config)
                member_policy = load_policy(serialized_member_policy)
                instantiated_policies.append(member_policy)
            except PolicyLoadError as e:
                raise PolicyLoadError(
                    f"Failed to load member policy at index {i} "
                    f"(name: {member_data.get('name', 'unknown')}) "
                    f"within SerialPolicy: {e}"
                ) from e
            except Exception as e:
                raise PolicyLoadError(
                    f"Unexpected error loading member policy at index {i} "
                    f"(name: {member_data.get('name', 'unknown')}) "
                    f"within SerialPolicy: {e}"
                ) from e

        name_val = config.get("name")
        resolved_name: Optional[str]
        if name_val is not None:
            if not isinstance(name_val, str):
                logger.warning(f"SerialPolicy name '{name_val}' from config is not a string. Coercing to string.")
                resolved_name = str(name_val)
            else:
                resolved_name = name_val
        else:
            # Default name if not in config. Could also use cls.__name__
            resolved_name = "SerialPolicy"

        return cls(policies=instantiated_policies, name=resolved_name)


# legacy compatibility
CompoundPolicy = SerialPolicy
