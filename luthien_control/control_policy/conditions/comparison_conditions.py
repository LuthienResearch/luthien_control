# pyright: reportCallIssue=false

"""
Comparison conditions for control policies.

This module implements comparison-based conditions (equals, contains, greater than, etc.)
using a clean ValueResolver pattern for flexible value resolution.

## Pyright Type Checker Suppression

The `# pyright: reportCallIssue=false` comment at the top of this file suppresses type
checker warnings for positional argument usage in comparison condition constructors.

### Why This Is Necessary

All comparison conditions inherit from Pydantic's BaseModel, which enforces keyword-only
constructors. However, we provide a more natural API with positional arguments:

```python
# Natural, concise syntax (what we want)
EqualsCondition(path("request.payload.model"), "gpt-4o")

# Verbose but type-safe (what Pydantic expects)
EqualsCondition(left=path("request.payload.model"), right="gpt-4o")
```

Our custom `__init__` methods handle both patterns correctly at runtime, but static
analysis tools like pyright cannot see through the Pydantic inheritance to understand
this flexibility.

### Safety Considerations

This suppression is safe because:
1. We only suppress `reportCallIssue` (constructor signature mismatches)
2. Our overload definitions provide proper type hints
3. Runtime behavior is thoroughly tested
4. Other type checking (return types, field access, etc.) remains active

### For Users of This Module

When using these comparison conditions in your code, you may encounter pyright warnings.
See the `ComparisonCondition` class documentation for guidance on suppressing these
warnings appropriately in your own files.
"""

from abc import ABC
from typing import Any, ClassVar, Literal, Union, overload

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
from luthien_control.core.transaction import Transaction


class ComparisonCondition(Condition, ABC):
    """
    Clean comparison condition that uses ValueResolver objects for flexible value resolution.

    This approach eliminates the need for is_dynamic_* flags by using explicit types.

    ## Constructor Usage

    This class supports both positional and keyword argument patterns:

    ### Positional Arguments (Recommended for brevity)
    ```python
    EqualsCondition(path("request.payload.model"), "gpt-4o")
    EqualsCondition(path("left_path"), path("right_path"))  # Dynamic comparison
    EqualsCondition("static_left", "static_right")          # Static comparison
    ```

    ### Keyword Arguments (Explicit, type-safe)
    ```python
    EqualsCondition(left=path("request.payload.model"), right="gpt-4o")
    EqualsCondition(left=path("left_path"), right=path("right_path"))
    ```

    ## Pyright Type Checker Warning

    **Important**: When using positional arguments, pyright may show this error:
    ```
    Expected 0 positional arguments (reportCallIssue)
    ```

    This is a known issue due to the underlying Pydantic BaseModel inheritance. The code
    works correctly at runtime, but pyright's static analysis doesn't recognize our
    custom `__init__` override.

    ### How to Suppress the Warning

    Add this comment to suppress the specific error on individual calls:
    ```python
    condition = EqualsCondition(path("test"), "value")  # pyright: ignore[reportCallIssue]
    ```

    Or add this at the top of your file to suppress all such errors in that file:
    ```python
    # pyright: reportCallIssue=false
    ```

    ### When to Use Each Approach

    - **Use positional**: For concise, readable condition creation in tests and simple cases
    - **Use keywords**: When you need full type safety or when working in strict typing environments
    - **Suppress warnings**: When you prefer the positional syntax and understand the trade-off
    """

    comparator: ClassVar[Comparator]

    left: ValueResolver
    right: ValueResolver
    comparator_name: str = Field(alias="comparator")

    @overload
    def __init__(self, left: Union[Any, ValueResolver], right: Union[Any, ValueResolver]) -> None: ...

    @overload
    def __init__(self, *, left: ValueResolver, right: ValueResolver, comparator: str, **kwargs: Any) -> None: ...

    def __init__(
        self,
        left: Union[Any, ValueResolver, None] = None,
        right: Union[Any, ValueResolver, None] = None,
        *,
        # Pydantic keyword-only arguments
        comparator: Union[str, None] = None,
        **kwargs,
    ):
        """Initialize with both positional and keyword argument support."""
        # Handle positional arguments
        if left is not None and right is not None:
            kwargs["left"] = auto_resolve_value(left)
            kwargs["right"] = auto_resolve_value(right)
            if comparator is None:
                kwargs["comparator"] = COMPARATOR_TO_NAME[type(self).comparator]
            else:
                kwargs["comparator"] = comparator
        elif "left" in kwargs and "right" in kwargs:
            # Already have keyword arguments, just ensure comparator is set
            if "comparator" not in kwargs:
                kwargs["comparator"] = COMPARATOR_TO_NAME[type(self).comparator]

        super().__init__(**kwargs)

    @field_serializer("left", "right")
    def serialize_value_resolver(self, value: ValueResolver) -> dict:
        """Custom serializer for ValueResolver fields."""
        return value.serialize()

    @field_validator("left", "right", mode="before")
    @classmethod
    def validate_value_resolver(cls, value):
        """Custom validator to deserialize ValueResolver from dict."""
        if isinstance(value, dict):
            return create_value_resolver(value)
        elif isinstance(value, ValueResolver):
            if isinstance(value, StaticValue) and isinstance(value.value, dict) and "type" in value.value:
                return create_value_resolver(value.value)
            return value
        else:
            return auto_resolve_value(value)

    def evaluate(self, transaction: Transaction) -> bool:
        """Evaluate the condition against the transaction."""
        left_value = self.left.resolve(transaction)
        right_value = self.right.resolve(transaction)
        return type(self).comparator.evaluate(left_value, right_value)

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self.left!r}, {self.right!r})"

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
