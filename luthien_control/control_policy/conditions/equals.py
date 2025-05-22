from typing import Any

from luthien_control.control_policy.conditions.condition import Condition
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.transaction_context import TransactionContext, TransactionMember


class EqualsCondition(Condition):
    type = "equals"

    def __init__(self, member: TransactionMember, key: str, value: Any):
        self.member = member
        self.key = key
        self.value = value

    def evaluate(self, context: TransactionContext) -> bool:
        target = getattr(context, self.member)
        if target is None:
            return False
        return target.get(self.key) == self.value

    def serialize(self) -> SerializableDict:
        return {
            "type": self.type,
            "value": self.value,
        }

    @classmethod
    def from_serialized(cls, serialized: SerializableDict) -> "EqualsCondition":
        return cls(serialized["value"])
