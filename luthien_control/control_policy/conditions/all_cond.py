from typing import List, Literal

from pydantic import Field, field_serializer, field_validator

from luthien_control.control_policy.conditions.condition import Condition
from luthien_control.core.transaction import Transaction


class AllCondition(Condition):
    type: Literal["all"] = "all"
    conditions: List[Condition] = Field(...)

    @field_serializer("conditions")
    def serialize_conditions(self, value: List[Condition]) -> List[dict]:
        """Custom serializer for conditions field."""
        return [condition.serialize() for condition in value]

    @field_validator("conditions", mode="before")
    @classmethod
    def validate_conditions(cls, value):
        """Custom validator to deserialize conditions from dicts."""
        if isinstance(value, list):
            result = []
            for item in value:
                if isinstance(item, dict):
                    result.append(Condition.from_serialized(item))
                elif isinstance(item, Condition):
                    result.append(item)
            return result
        return value

    def evaluate(self, transaction: Transaction) -> bool:
        return all(condition.evaluate(transaction) for condition in self.conditions)
