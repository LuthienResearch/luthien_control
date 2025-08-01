from typing import Literal

from pydantic import Field, field_serializer, field_validator

from luthien_control.control_policy.conditions.condition import Condition
from luthien_control.core.transaction import Transaction


class NotCondition(Condition):
    type: Literal["not"] = "not"
    cond: Condition = Field(...)

    @field_serializer("cond")
    def serialize_cond(self, value: Condition) -> dict:
        """Custom serializer for cond field."""
        return value.serialize()

    @field_validator("cond", mode="before")
    @classmethod
    def validate_cond(cls, value):
        """Custom validator to deserialize condition from dict."""
        if isinstance(value, dict):
            return Condition.from_serialized(value)
        return value

    def evaluate(self, transaction: Transaction) -> bool:
        return not self.cond.evaluate(transaction)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(value={self.cond!r})"
