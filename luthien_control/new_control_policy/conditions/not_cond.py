from luthien_control.core.transaction import Transaction
from luthien_control.new_control_policy.conditions.condition import Condition
from luthien_control.new_control_policy.serialization import SerializableDict


class NotCondition(Condition):
    type = "not"

    def __init__(self, value: Condition):
        self.cond = value

    def evaluate(self, transaction: Transaction) -> bool:
        return not self.cond.evaluate(transaction)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(value={self.cond!r})"

    def serialize(self) -> SerializableDict:
        return {
            "type": self.type,
            "value": self.cond.serialize(),
        }

    @classmethod
    def from_serialized(cls, serialized: SerializableDict) -> "NotCondition":
        from luthien_control.new_control_policy.conditions.util import get_condition_from_serialized

        nested_condition_config = serialized.get("value")
        if not isinstance(nested_condition_config, dict):
            raise TypeError(
                f"Configuration for NotCondition's nested condition ('value') must be a dictionary. "
                f"Got: {nested_condition_config!r} (type: {type(nested_condition_config).__name__})"
            )

        cond = get_condition_from_serialized(nested_condition_config)
        return cls(cond)
