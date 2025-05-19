from abc import ABC
from typing import Any, ClassVar

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
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.transaction_context import TransactionContext, get_tx_value


class ComparisonCondition(Condition, ABC):
    type: ClassVar[str]  # To be defined by concrete subclasses
    comparator: ClassVar[Comparator]  # To be defined by concrete subclasses

    key: str
    value: Any

    def __init__(self, key: str, value: Any):
        """
        Args:
            key: The key to the value to compare against in the transaction context (see get_tx_value)
            value: The value to compare against the key.

        Example:
            key = "request.data.user"
            value = "John"
        """
        self.key = key
        self.value = value

    def evaluate(self, context: TransactionContext) -> bool:
        return type(self).comparator.evaluate(get_tx_value(context, self.key), self.value)

    def __repr__(self) -> str:
        return f"{type(self).__name__}(key={self.key!r}, value={self.value!r})"

    def serialize(self) -> SerializableDict:
        return {
            "type": type(self).type,
            "key": self.key,
            "comparator": COMPARATOR_TO_NAME[type(self).comparator],
            "value": self.value,
        }

    @classmethod
    def from_serialized(cls, serialized: SerializableDict) -> "ComparisonCondition":
        key_val = serialized.get("key")
        if not isinstance(key_val, str):
            raise TypeError(
                f"Configuration for {cls.__name__} is missing 'key' or it is not a string. "
                f"Got: {key_val!r} (type: {type(key_val).__name__})"
            )

        value_val = serialized.get("value")

        return cls(key=key_val, value=value_val)


class EqualsCondition(ComparisonCondition):
    """
    Condition to check if a value is equal to another value.

    Example:
        key = "request.content.model"
        value = "gpt-4o"

        Matches when the value of `'content'` in `request.content` is "gpt-4o"
    """

    type = "equals"
    comparator = equals


class NotEqualsCondition(ComparisonCondition):
    """
    Condition to check if a value is *NOT* equal to another value.

    Example:
        key = "request.content.model"
        value = "gpt-4o"

        Matches when the value of `'content'` in `request.content` is NOT "gpt-4o"
    """

    type = "not_equals"
    comparator = not_equals


class ContainsCondition(ComparisonCondition):
    """
    Condition to check if a value contains another value.

    Example:
        key = "response.completion_tokens_details"
        value = "audio_tokens"

        Matches when the `completion_tokens_details` in the response contains "audio_tokens"
    """

    type = "contains"
    comparator = contains


class LessThanCondition(ComparisonCondition):
    """
    Condition to check if a value is less than another value.

    Example:
        key = "response.content.created"
        value = 1741569952  # 2025-01-01 00:00:00 UTC

        Matches when the timestamp of the response is before 2025-01-01 00:00:00 UTC
    """

    type = "less_than"
    comparator = less_than


class LessThanOrEqualCondition(ComparisonCondition):
    """
    Condition to check if a value is less than or equal to another value.

    Example:
        key = "response.content.created"
        value = 1741569952  # 2025-01-01 00:00:00 UTC

        Matches when the timestamp of the response is before or equal to 2025-01-01 00:00:00 UTC
    """

    type = "less_than_or_equal"
    comparator = less_than_or_equal


class GreaterThanCondition(ComparisonCondition):
    """
    Condition to check if a value is greater than another value.

    Example:
        key = "response.content.created"
        value = 1741569952  # 2025-01-01 00:00:00 UTC

        Matches when the timestamp of the response is after 2025-01-01 00:00:00 UTC
    """

    type = "greater_than"
    comparator = greater_than


class GreaterThanOrEqualCondition(ComparisonCondition):
    """
    Condition to check if a value is greater than or equal to another value.

    Example:
        key = "response.content.created"
        value = 1741569952  # 2025-01-01 00:00:00 UTC

        Matches when the timestamp of the response is after or equal to 2025-01-01 00:00:00 UTC
    """

    type = "greater_than_or_equal"
    comparator = greater_than_or_equal


class RegexMatchCondition(ComparisonCondition):
    """
    Condition to check if a value matches a regular expression.

    Example:
        key = "request.content.model"
        value = "gpt-4"

        Matches when the model specified in the request contains "gpt-4"
    """

    type = "regex_match"
    comparator = regex_match
