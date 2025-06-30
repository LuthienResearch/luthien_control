from typing import ClassVar, Literal

from pydantic import Field, field_serializer, field_validator

from luthien_control.control_policy.conditions.condition import Condition
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.transaction import Transaction


class NotCondition(Condition):
    type: ClassVar[str] = "not"
    cond: Condition = Field(...)

    def __init__(self, value: Condition | None = None, **data):
        """
        Args:
            value: The condition to negate
        """
        if value is not None:
            data['cond'] = value
        
        super().__init__(**data)

    @field_serializer('cond', when_used='json')
    def serialize_cond(self, value: Condition) -> dict:
        """Custom serializer for cond field."""
        return value.serialize()
    
    def serialize(self) -> SerializableDict:
        """Override serialize to use 'value' field name for backward compatibility."""
        data = super().serialize()
        if 'cond' in data:
            data['value'] = data.pop('cond')
        return data

    @field_validator('cond', mode='before')
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
