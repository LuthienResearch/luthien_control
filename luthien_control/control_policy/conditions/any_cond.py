from typing import ClassVar, List

from pydantic import Field, field_serializer, field_validator

from luthien_control.control_policy.conditions.condition import Condition
from luthien_control.core.transaction import Transaction


class AnyCondition(Condition):
    type: ClassVar[str] = "any"
    conditions: List[Condition] = Field(...)

    def __init__(self, conditions: List[Condition] | None = None, **data):
        """
        Args:
            conditions: List of conditions where at least one must be true
        """
        if conditions is not None:
            data['conditions'] = conditions

        super().__init__(**data)

    @field_serializer('conditions')
    def serialize_conditions(self, value: List[Condition]) -> List[dict]:
        """Custom serializer for conditions field."""
        return [condition.serialize() for condition in value]

    @field_validator('conditions', mode='before')
    @classmethod
    def validate_conditions(cls, value):
        """Custom validator to deserialize conditions from dicts."""
        if isinstance(value, list):
            result = []
            for item in value:
                if isinstance(item, dict):
                    result.append(Condition.from_serialized(item))
                else:
                    result.append(item)
            return result
        return value

    def evaluate(self, transaction: Transaction) -> bool:
        return any(condition.evaluate(transaction) for condition in self.conditions)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(conditions={self.conditions!r})"
