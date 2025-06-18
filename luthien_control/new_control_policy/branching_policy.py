import json
import logging
from collections import OrderedDict
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction import Transaction
from luthien_control.new_control_policy.conditions.condition import Condition
from luthien_control.new_control_policy.control_policy import ControlPolicy
from luthien_control.new_control_policy.serialization import SerializableDict

logger = logging.getLogger(__name__)


class BranchingPolicy(ControlPolicy):
    """
    A Control Policy that conditionally applies different policies based on transaction evaluation.

    This policy evaluates conditions in order and applies the policy associated with the first
    matching condition. If no conditions match, it applies the default policy (if configured).

    Serialization approach:
    - Overrides serialize() directly for full control over complex nested structure serialization
    - Does NOT use _get_policy_specific_config() (only used by simple policies)
    - Serialized form includes: 'type', 'name', 'cond_to_policy_map', and 'default_policy'
    - Container policies like this need custom serialization to handle nested structures
    """

    def __init__(
        self,
        cond_to_policy_map: OrderedDict[Condition, ControlPolicy],
        default_policy: Optional[ControlPolicy] = None,
        name: Optional[str] = None,
    ):
        super().__init__(name=name, cond_to_policy_map=cond_to_policy_map, default_policy=default_policy)
        self.cond_to_policy_map = cond_to_policy_map
        self.default_policy = default_policy

    async def apply(
        self, transaction: Transaction, container: DependencyContainer, session: AsyncSession
    ) -> Transaction:
        """
        Apply the first policy that matches the condition. If no condition matches, apply the default policy (if set).

        Args:
            transaction: The transaction to apply the policy to.
            container: The dependency container.
            session: The database session.

        Returns:
            The potentially modified transaction.
        """
        for cond, policy in self.cond_to_policy_map.items():
            if cond.evaluate(transaction):
                return await policy.apply(transaction, container, session)
        if self.default_policy:
            return await self.default_policy.apply(transaction, container, session)
        return transaction

    def serialize(self) -> SerializableDict:
        """Serializes the BranchingPolicy into a dictionary.

        This is a container policy that overrides serialize() directly rather than
        using _get_policy_specific_config() because it needs to serialize complex nested
        structures (conditions and policies), which requires more specialized logic
        than the template method can handle.

        Returns:
            SerializableDict: A dictionary representation containing:
                - 'type': The policy type name from the registry
                - 'name': The policy instance name (if set)
                - 'cond_to_policy_map': Dict mapping JSON-serialized conditions to policies
                - 'default_policy': Serialized default policy (if set) or None
        """
        result: SerializableDict = {
            "type": self.get_policy_type_name(),
            "cond_to_policy_map": {
                json.dumps(cond.serialize()): policy.serialize() for cond, policy in self.cond_to_policy_map.items()
            },
            "default_policy": self.default_policy.serialize() if self.default_policy else None,
        }
        if self.name is not None:
            result["name"] = self.name
        return result

    @classmethod
    def from_serialized(cls, config: SerializableDict) -> "BranchingPolicy":
        cond_to_policy_map = OrderedDict()

        serialized_cond_map = config.get("cond_to_policy_map")
        if not isinstance(serialized_cond_map, dict):
            raise TypeError(
                f"Expected 'cond_to_policy_map' to be a dict in BranchingPolicy config, got {type(serialized_cond_map)}"
            )

        # The keys of serialized_cond_map are expected to be JSON strings of condition configs
        # The values are expected to be policy configs (SerializableDict)
        for cond_json_str, policy_config in serialized_cond_map.items():
            if not isinstance(cond_json_str, str):
                raise TypeError(
                    f"Condition key in 'cond_to_policy_map' must be a JSON string, got {type(cond_json_str)}"
                )

            if not isinstance(policy_config, dict):
                raise TypeError(
                    f"Policy config for condition '{cond_json_str}' must be a dict, got {type(policy_config)}"
                )

            try:
                condition_serializable_dict = json.loads(cond_json_str)
            except json.JSONDecodeError as e:
                raise ValueError(f"Failed to parse condition JSON string '{cond_json_str}': {e}")

            if not isinstance(condition_serializable_dict, dict):
                raise TypeError(
                    f"Deserialized condition config for '{cond_json_str}' must be a dict, "
                    f"got {type(condition_serializable_dict)}"
                )

            condition = Condition.from_serialized(condition_serializable_dict)
            policy = ControlPolicy.from_serialized(policy_config)
            cond_to_policy_map[condition] = policy

        default_policy_serializable = config.get("default_policy")
        default_policy: Optional[ControlPolicy] = None
        if default_policy_serializable is not None:
            if not isinstance(default_policy_serializable, dict):
                raise TypeError(
                    f"Expected 'default_policy' config to be a dict, got {type(default_policy_serializable)}"
                )
            default_policy = ControlPolicy.from_serialized(default_policy_serializable)

        instance_name = config.get("name")
        resolved_name: Optional[str] = None
        if instance_name is not None:
            if not isinstance(instance_name, str):
                raise TypeError(f"BranchingPolicy name must be a string, got {type(instance_name)}")
            resolved_name = instance_name

        return cls(cond_to_policy_map=cond_to_policy_map, default_policy=default_policy, name=resolved_name)
