from luthien_control.control_policy.conditions.condition import Condition
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.transaction_context import TransactionContext


class NotCondition(Condition):
    type = "not"

    def __init__(self, value: Condition):
        self.cond = value

    def evaluate(self, context: TransactionContext) -> bool:
        return not self.cond.evaluate(context)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(value={self.cond!r})"

    def serialize(self) -> SerializableDict:
        return {
            "type": self.type,
            "value": self.cond.serialize(),
        }

    @classmethod
    def from_serialized(cls, serialized: SerializableDict) -> "NotCondition":
        from luthien_control.control_policy.conditions.util import get_condition_from_serialized

        cond = get_condition_from_serialized(serialized["value"])
        return cls(cond)
