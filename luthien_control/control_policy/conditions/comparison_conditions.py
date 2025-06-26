from abc import ABC
from typing import Any, ClassVar, Union

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

    type: ClassVar[str]
    comparator: ClassVar[Comparator]

    def __init__(self, left: Union[Any, ValueResolver], right: Union[Any, ValueResolver]):
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
        self.left_resolver = auto_resolve_value(left)
        self.right_resolver = auto_resolve_value(right)

    def evaluate(self, transaction: Transaction) -> bool:
        """Evaluate the condition against the transaction."""
        left_value = self.left_resolver.resolve(transaction)
        right_value = self.right_resolver.resolve(transaction)
        return type(self).comparator.evaluate(left_value, right_value)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.left_resolver!r}, {self.right_resolver!r})"

    def serialize(self) -> SerializableDict:
        """Serialize the condition to a dictionary."""
        return {
            "type": type(self).type,
            "left": self.left_resolver.serialize(),
            "right": self.right_resolver.serialize(),
            "comparator": COMPARATOR_TO_NAME[type(self).comparator],
        }

    @classmethod
    def from_serialized(cls, serialized: SerializableDict) -> "ComparisonCondition":
        """Create a condition from serialized data."""
        left_data = serialized.get("left")
        right_data = serialized.get("right")

        if not isinstance(left_data, dict) or not isinstance(right_data, dict):
            raise TypeError("Left and right must be serialized ValueResolver objects")

        left_resolver = create_value_resolver(left_data)
        right_resolver = create_value_resolver(right_data)

        # Create instance using the resolved values directly
        instance = cls.__new__(cls)
        instance.left_resolver = left_resolver
        instance.right_resolver = right_resolver
        return instance

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
        return cls(path(key), value)


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

    type = "equals"
    comparator = equals


class NotEqualsCondition(ComparisonCondition):
    """
    Condition to check if two values are NOT equal.
    """

    type = "not_equals"
    comparator = not_equals


class ContainsCondition(ComparisonCondition):
    """
    Condition to check if the left value contains the right value.
    """

    type = "contains"
    comparator = contains


class LessThanCondition(ComparisonCondition):
    """
    Condition to check if the left value is less than the right value.
    """

    type = "less_than"
    comparator = less_than


class LessThanOrEqualCondition(ComparisonCondition):
    """
    Condition to check if the left value is less than or equal to the right value.
    """

    type = "less_than_or_equal"
    comparator = less_than_or_equal


class GreaterThanCondition(ComparisonCondition):
    """
    Condition to check if the left value is greater than the right value.
    """

    type = "greater_than"
    comparator = greater_than


class GreaterThanOrEqualCondition(ComparisonCondition):
    """
    Condition to check if the left value is greater than or equal to the right value.
    """

    type = "greater_than_or_equal"
    comparator = greater_than_or_equal


class RegexMatchCondition(ComparisonCondition):
    """
    Condition to check if the left value matches a regex pattern.
    """

    type = "regex_match"
    comparator = regex_match
