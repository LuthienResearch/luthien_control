from abc import ABC
from typing import Any, ClassVar, Literal, Union

from pydantic import Field, field_serializer, field_validator

from luthien_control.control_policy.conditions.comparators import (
    COMPARATOR_TO_NAME,
    Comparator,
    contains,
    equals,
    greater_than,
    greater_than_or_equal,
    less_than,
    less_than_or_equal,
    not_equals,
    regex_match,
)
from luthien_control.control_policy.conditions.condition import Condition
from luthien_control.control_policy.conditions.value_resolvers import (
    StaticValue,
    ValueResolver,
    auto_resolve_value,
    create_value_resolver,
    path,
)
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.transaction import Transaction


class ComparisonCondition(Condition, ABC):
    """
    Clean comparison condition that uses ValueResolver objects for flexible value resolution.

    This approach eliminates the need for is_dynamic_* flags by using explicit types.
    """

    comparator: ClassVar[Comparator]
    
    left_resolver: ValueResolver = Field(..., alias="left")
    right_resolver: ValueResolver = Field(..., alias="right")
    comparator_name: str = Field(..., alias="comparator")

    @field_serializer('left_resolver', 'right_resolver')
    def serialize_value_resolver(self, value: ValueResolver) -> dict:
        """Custom serializer for ValueResolver fields."""
        return value.serialize()

    @field_validator('left_resolver', 'right_resolver', mode='before')
    @classmethod
    def validate_value_resolver(cls, value):
        """Custom validator to deserialize ValueResolver from dict."""
        if isinstance(value, dict):
            return create_value_resolver(value)
        elif isinstance(value, ValueResolver):
            if isinstance(value, StaticValue) and isinstance(value.value, dict) and 'type' in value.value:
                return create_value_resolver(value.value)
            return value
        else:
            return auto_resolve_value(value)

    def __init__(self, left: Union[Any, ValueResolver] = None, right: Union[Any, ValueResolver] = None, **data):
        """
        Args:
            left: Either a static value or a ValueResolver (e.g., path("request.payload.model"))
            right: Either a static value or a ValueResolver (e.g., path("data.preferred_model"))

        Examples:
            # Traditional: transaction path vs static value
            EqualsCondition(path("request.payload.model"), "gpt-4o")

            # Dynamic: transaction path vs transaction path
            EqualsCondition(path("request.payload.model"), path("data.preferred_model"))

            # Static vs transaction path
            EqualsCondition("gpt-4o", path("request.payload.model"))

            # Static vs static
            EqualsCondition("gpt-4o", "gpt-4o")
        """
        if left is not None and right is not None and 'left' not in data and 'right' not in data:
            left_resolver = auto_resolve_value(left)
            right_resolver = auto_resolve_value(right)
            comparator_name = COMPARATOR_TO_NAME[type(self).comparator]
            data.update({
                'left': left_resolver,
                'right': right_resolver,
                'comparator': comparator_name
            })
        
        if 'comparator' not in data:
            data['comparator'] = COMPARATOR_TO_NAME[type(self).comparator]
        
        super().__init__(**data)

    def evaluate(self, transaction: Transaction) -> bool:
        """Evaluate the condition against the transaction."""
        left_value = self.left_resolver.resolve(transaction)
        right_value = self.right_resolver.resolve(transaction)
        return type(self).comparator.evaluate(left_value, right_value)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.left_resolver!r}, {self.right_resolver!r})"

    @classmethod
    def from_serialized(cls, serialized: SerializableDict) -> "ComparisonCondition":
        """Create a condition from serialized data."""
        left_data = serialized.get("left")
        right_data = serialized.get("right")

        if not isinstance(left_data, dict) or not isinstance(right_data, dict):
            raise TypeError("Left and right must be serialized ValueResolver objects")

        left_resolver = create_value_resolver(left_data)
        right_resolver = create_value_resolver(right_data)

        return cls(left=left_resolver, right=right_resolver)

    @classmethod
    def from_legacy_format(cls, key: str, value: Any) -> "ComparisonCondition":
        """
        Create a condition from legacy ComparisonCondition format.

        Args:
            key: Transaction path (e.g., "request.payload.model")
            value: Static value to compare against

        Returns:
            A ComparisonCondition instance
        """
        return cls(left=path(key), right=value)


class EqualsCondition(ComparisonCondition):
    """
    Condition to check if two values are equal.

    Examples:
        # Traditional
        EqualsCondition(path("request.payload.model"), "gpt-4o")

        # Dynamic
        EqualsCondition(path("request.payload.model"), path("data.preferred_model"))

        # Static vs dynamic
        EqualsCondition("gpt-4o", path("request.payload.model"))
    """

    type: Literal["equals"] = Field(default="equals")
    comparator = equals


class NotEqualsCondition(ComparisonCondition):
    """
    Condition to check if two values are NOT equal.
    """

    type: Literal["not_equals"] = Field(default="not_equals")
    comparator = not_equals


class ContainsCondition(ComparisonCondition):
    """
    Condition to check if the left value contains the right value.
    """

    type: Literal["contains"] = Field(default="contains")
    comparator = contains


class LessThanCondition(ComparisonCondition):
    """
    Condition to check if the left value is less than the right value.
    """

    type: Literal["less_than"] = Field(default="less_than")
    comparator = less_than


class LessThanOrEqualCondition(ComparisonCondition):
    """
    Condition to check if the left value is less than or equal to the right value.
    """

    type: Literal["less_than_or_equal"] = Field(default="less_than_or_equal")
    comparator = less_than_or_equal


class GreaterThanCondition(ComparisonCondition):
    """
    Condition to check if the left value is greater than the right value.
    """

    type: Literal["greater_than"] = Field(default="greater_than")
    comparator = greater_than


class GreaterThanOrEqualCondition(ComparisonCondition):
    """
    Condition to check if the left value is greater than or equal to the right value.
    """

    type: Literal["greater_than_or_equal"] = Field(default="greater_than_or_equal")
    comparator = greater_than_or_equal


class RegexMatchCondition(ComparisonCondition):
    """
    Condition to check if the left value matches a regex pattern.
    """

    type: Literal["regex_match"] = Field(default="regex_match")
    comparator = regex_match
