from typing import List

from luthien_control.control_policy.conditions.condition import Condition
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.tracked_context import TrackedContext


class AllCondition(Condition):
    type = "all"

    def __init__(self, conditions: List[Condition]):
        self.conditions = conditions

    def evaluate(self, context: TrackedContext) -> bool:
        return all(condition.evaluate(context) for condition in self.conditions)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(conditions={self.conditions!r})"

    def serialize(self) -> SerializableDict:
        return {
            "type": self.type,
            "conditions": [condition.serialize() for condition in self.conditions],
        }

    @classmethod
    def from_serialized(cls, serialized: SerializableDict) -> "AllCondition":
        from luthien_control.control_policy.conditions.util import get_conditions_from_serialized

        conds = get_conditions_from_serialized(serialized)
        return cls(conds)
