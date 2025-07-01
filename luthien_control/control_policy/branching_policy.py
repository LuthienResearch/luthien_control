import json
import logging
from collections import OrderedDict
from typing import Optional

from pydantic import Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from luthien_control.control_policy.conditions.condition import Condition
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction import Transaction

logger = logging.getLogger(__name__)


class BranchingPolicy(ControlPolicy):
    """
    A Control Policy that conditionally applies different policies based on transaction evaluation.

    This policy evaluates conditions in order and applies the policy associated with the first
    matching condition. If no conditions match, it applies the default policy (if configured).
    """

    name: Optional[str] = Field(default="BranchingPolicy")
    cond_to_policy_map: OrderedDict[Condition, ControlPolicy] = Field(default_factory=OrderedDict, exclude=True)
    default_policy: Optional[ControlPolicy] = Field(default=None)

    @field_validator("cond_to_policy_map", mode="before")
    @classmethod
    def validate_cond_to_policy_map(cls, value):
        """Validate and convert condition-to-policy mapping."""
        if isinstance(value, OrderedDict):
            return value
        if isinstance(value, dict):
            return OrderedDict(value)
        raise ValueError("cond_to_policy_map must be a dict or OrderedDict")

    @field_validator("default_policy", mode="before")
    @classmethod
    def validate_default_policy(cls, value):
        """Validate default policy field."""
        return value

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
        """Override serialize to handle complex condition-to-policy mapping."""
        data = super().serialize()
        data["cond_to_policy_map"] = {
            json.dumps(cond.serialize()): policy.serialize() for cond, policy in self.cond_to_policy_map.items()
        }
        if self.default_policy:
            data["default_policy"] = self.default_policy.serialize()
        else:
            data["default_policy"] = None
        return data

    @classmethod
    def from_serialized(cls, config: SerializableDict) -> "BranchingPolicy":
        """Custom from_serialized to handle JSON-serialized condition keys."""
        config_copy = dict(config)

        cond_to_policy_map = OrderedDict()
        serialized_cond_map = config_copy.pop("cond_to_policy_map", None)
        if serialized_cond_map is not None:
            if not isinstance(serialized_cond_map, dict):
                raise TypeError(
                    f"Expected 'cond_to_policy_map' to be a dict in BranchingPolicy config, "
                    f"got {type(serialized_cond_map)}"
                )

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

        default_policy = None
        default_policy_serializable = config_copy.pop("default_policy", None)
        if default_policy_serializable is not None:
            if not isinstance(default_policy_serializable, dict):
                raise TypeError(
                    f"Expected 'default_policy' config to be a dict, got {type(default_policy_serializable)}"
                )
            default_policy = ControlPolicy.from_serialized(default_policy_serializable)

        instance = super().from_serialized(config_copy)

        instance.cond_to_policy_map = cond_to_policy_map
        instance.default_policy = default_policy

        return instance
