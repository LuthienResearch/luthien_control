# Serial Policy that applies a sequence of other policies.

from typing import Iterable, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction import Transaction
from luthien_control.new_control_policy.control_policy import ControlPolicy
from luthien_control.new_control_policy.exceptions import PolicyLoadError
from luthien_control.new_control_policy.serialization import SerializableDict, SerializedPolicy


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
        super().__init__(name=name, policies=policies)
        if not policies:
            self.logger.warning(f"Initializing SerialPolicy '{name}' with an empty policy list.")
        self.policies = policies
        self.name = name or self.__class__.__name__

    async def apply(
        self,
        transaction: Transaction,
        container: DependencyContainer,
        session: AsyncSession,
    ) -> Transaction:
        """
        Applies the contained policies sequentially to the transaction.
        Requires the DependencyContainer and an active SQLAlchemy AsyncSession.

        Args:
            transaction: The current transaction.
            container: The application dependency container.
            session: An active SQLAlchemy AsyncSession, passed to member policies.

        Returns:
            The transaction after all contained policies have been applied.

        Raises:
            Exception: Propagates any exception raised by a contained policy.
        """
        self.logger.debug(f"Entering SerialPolicy: {self.name}")
        current_transaction = transaction
        for i, policy in enumerate(self.policies):
            member_policy_name = getattr(policy, "name", policy.__class__.__name__)  # Get policy name if available
            self.logger.info(f"Applying policy {i + 1}/{len(self.policies)} in {self.name}: {member_policy_name}")
            try:
                current_transaction = await policy.apply(current_transaction, container=container, session=session)
            except Exception as e:
                self.logger.error(
                    f"Error applying policy {member_policy_name} within {self.name}: {e}",
                    exc_info=True,
                )
                raise  # Re-raise the exception to halt processing
        self.logger.debug(f"Exiting SerialPolicy: {self.name}")
        return current_transaction

    def __repr__(self) -> str:
        """Provides a developer-friendly representation."""
        # Get the name of each policy, using getattr as fallback like in apply
        policy_reprs = [f"{p.name} <{p.__class__.__name__}>" for p in self.policies]
        policy_list_str = ", ".join(policy_reprs)
        return f"<{self.name}(policies=[{policy_list_str}])>"

    def _get_policy_specific_config(self) -> SerializableDict:
        return SerializableDict(
            {
                "policies": [p.serialize() for p in self.policies],
            }
        )

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

            try:
                # Import load_policy to properly handle member policy loading
                from luthien_control.new_control_policy.loader import load_policy

                # Get the type and config from member_data
                member_type = member_data.get("type")
                member_config = member_data.get("config", {})

                if not isinstance(member_type, str):
                    raise PolicyLoadError(
                        f"Member policy at index {i} must have a 'type' field as string. Got: {type(member_type)}"
                    )
                if not isinstance(member_config, dict):
                    raise PolicyLoadError(
                        f"Member policy at index {i} must have a 'config' field as dict. Got: {type(member_config)}"
                    )

                # If name is at the top level (legacy format), move it to config
                if "name" in member_data and "name" not in member_config:
                    member_config["name"] = member_data.get("name")

                # Create SerializedPolicy object from member_data
                serialized_member = SerializedPolicy(type=member_type, config=member_config)
                member_policy = load_policy(serialized_member)
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
                resolved_name = str(name_val)
            else:
                resolved_name = name_val
        else:
            # Default name if not in config. Could also use cls.__name__
            resolved_name = "SerialPolicy"

        return cls(policies=instantiated_policies, name=resolved_name)


# legacy compatibility
CompoundPolicy = SerialPolicy
