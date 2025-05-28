import json
import logging
from collections import OrderedDict
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.conditions.condition import Condition
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction_context import TransactionContext

logger = logging.getLogger(__name__)


class BranchingPolicy(ControlPolicy):
    def __init__(
        self,
        cond_to_policy_map: OrderedDict[Condition, ControlPolicy],
        default_policy: Optional[ControlPolicy] = None,
        name: Optional[str] = None,
    ):
        self.name = name
        self.cond_to_policy_map = cond_to_policy_map
        self.default_policy = default_policy

    async def apply(
        self, context: TransactionContext, container: DependencyContainer, session: AsyncSession
    ) -> TransactionContext:
        """
        Apply the first policy that matches the condition. If no condition matches, apply the default policy (if set).

        Args:
            context: The transaction context to apply the policy to.
            container: The dependency container.
            session: The database session.

        Returns:
            The potentially modified transaction context.
        """
        for cond, policy in self.cond_to_policy_map.items():
            if cond.evaluate(context):
                return await policy.apply(context, container, session)
        if self.default_policy:
            return await self.default_policy.apply(context, container, session)
        return context

    def serialize(self) -> SerializableDict:
        result: SerializableDict = {
            "type": "branching",
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

            # Assuming Condition.from_serialized and ControlPolicy.from_serialized
            # expect SerializableDict (which is Dict[str, Union[SP, List[Any], Dict[str, Any], None]])
            # The isinstance(..., dict) checks are sufficient for pyright to allow passage
            # to functions expecting Dict[str, X] or Mapping[str, X].
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
