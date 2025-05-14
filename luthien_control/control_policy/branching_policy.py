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

        Raises:
            Exception:
        """
        for cond, policy in self.cond_to_policy_map.items():
            if cond.evaluate(context):
                return await policy.apply(context, container, session)
        if self.default_policy:
            return await self.default_policy.apply(context, container, session)
        else:
            logger.warning("No policy matched, returning original context")
        return context

    def serialize(self) -> SerializableDict:
        return {
            "type": "branching",
            "cond_to_policy_map": {
                cond.serialize(): policy.serialize() for cond, policy in self.cond_to_policy_map.items()
            },
            "default_policy": self.default_policy.serialize() if self.default_policy else None,
        }

    @classmethod
    async def from_serialized(cls, config: SerializableDict) -> "BranchingPolicy":
        cond_to_policy_map = {
            Condition.from_serialized(cond): ControlPolicy.from_serialized(policy)
            for cond, policy in config["cond_to_policy_map"].items()
        }
        default_policy = ControlPolicy.from_serialized(config["default_policy"]) if config["default_policy"] else None
        return cls(cond_to_policy_map, default_policy)
