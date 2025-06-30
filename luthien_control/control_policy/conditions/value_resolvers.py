from abc import ABC, abstractmethod
from typing import Any, Literal

from pydantic import BaseModel, Field

from luthien_control.control_policy.conditions.util import get_transaction_value
from luthien_control.control_policy.serialization import SerializableDict, safe_model_dump, safe_model_validate
from luthien_control.core.transaction import Transaction


class ValueResolver(BaseModel, ABC):
    """
    Abstract base class for resolving values from transactions.
    """

    type: str = Field(...)

    @abstractmethod
    def resolve(self, transaction: Transaction) -> Any:
        """
        Resolve and return a value from the transaction.

        Args:
            transaction: The transaction to resolve the value from

        Returns:
            The resolved value
        """
        pass

    def serialize(self) -> SerializableDict:
        """Serialize using Pydantic model_dump through SerializableDict validation."""
        return safe_model_dump(self)

    @classmethod
    def from_serialized(cls, serialized: SerializableDict) -> "ValueResolver":
        """
        Create a value resolver from a serialized dictionary.

        Args:
            serialized: The serialized representation

        Returns:
            A ValueResolver instance
        """
        return safe_model_validate(cls, serialized)

    class Config:
        arbitrary_types_allowed = True


class StaticValue(ValueResolver):
    """
    A static value that doesn't depend on the transaction.
    """

    type: Literal["static"] = Field(default="static")
    value: Any = Field(...)

    def __init__(self, value: Any = None, **data):
        """
        Args:
            value: The static value to return
        """
        if 'value' not in data and value is not None:
            data['value'] = value
        elif 'value' not in data and value is None:
            data['value'] = value
        
        super().__init__(**data)

    def resolve(self, transaction: Transaction) -> Any:
        """Return the static value."""
        return self.value

    def __repr__(self) -> str:
        return f"StaticValue(value={self.value!r})"

    def __eq__(self, other: object) -> bool:
        """Check equality with another StaticValue."""
        return isinstance(other, StaticValue) and self.value == other.value


class TransactionPath(ValueResolver):
    """
    A value resolver that extracts a value from a transaction using a path.
    """

    type: Literal["transaction_path"] = Field(default="transaction_path")
    path: str = Field(...)

    def __init__(self, path: str | None = None, **data):
        """
        Args:
            path: The path to the value in the transaction (e.g., "request.payload.model")
        """
        if path is not None:
            data['path'] = path
        
        super().__init__(**data)

    def resolve(self, transaction: Transaction) -> Any:
        """Resolve the value from the transaction using the path."""
        try:
            return get_transaction_value(transaction, self.path)
        except (AttributeError, ValueError):
            return None

    def __repr__(self) -> str:
        return f"TransactionPath(path={self.path!r})"

    def __eq__(self, other: object) -> bool:
        """Check equality with another TransactionPath."""
        return isinstance(other, TransactionPath) and self.path == other.path


# Registry for value resolver types
VALUE_RESOLVER_REGISTRY = {
    "static": StaticValue,
    "transaction_path": TransactionPath,
}


def create_value_resolver(serialized: SerializableDict) -> ValueResolver:
    """
    Create a value resolver from serialized data.

    Args:
        serialized: The serialized value resolver data

    Returns:
        A ValueResolver instance

    Raises:
        ValueError: If the resolver type is unknown
        KeyError: If the type field is missing
    """
    resolver_type = serialized.get("type")
    if resolver_type not in VALUE_RESOLVER_REGISTRY:
        raise ValueError(f"Unknown value resolver type: {resolver_type}")

    resolver_class = VALUE_RESOLVER_REGISTRY[resolver_type]
    return safe_model_validate(resolver_class, serialized)


def auto_resolve_value(value: Any) -> ValueResolver:
    """
    Automatically convert a value to an appropriate ValueResolver.

    Args:
        value: Either a static value or a ValueResolver instance

    Returns:
        A ValueResolver instance
    """
    if isinstance(value, ValueResolver):
        return value
    else:
        return StaticValue(value=value)


def path(transaction_path: str) -> TransactionPath:
    """
    Convenience function to create a TransactionPath.

    Args:
        transaction_path: The path to the value in the transaction

    Returns:
        A TransactionPath instance

    Example:
        path("request.payload.model")
    """
    return TransactionPath(path=transaction_path)
