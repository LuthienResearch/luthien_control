from typing import Any, List, Type, cast

from luthien_control.core.transaction import Transaction
from luthien_control.new_control_policy.conditions.condition import Condition
from luthien_control.new_control_policy.serialization import SerializableDict


def get_condition_class(name: str) -> Type[Condition]:
    from luthien_control.new_control_policy.conditions.registry import NAME_TO_CONDITION_CLASS

    return NAME_TO_CONDITION_CLASS[name]


def get_condition_class_from_serialized(serialized: SerializableDict) -> Type[Condition]:
    condition_type_name = str(serialized.get("type"))
    return get_condition_class(condition_type_name)


def get_condition_from_serialized(serialized: SerializableDict) -> Condition:
    return get_condition_class_from_serialized(serialized).from_serialized(serialized)


def get_conditions_from_serialized(serialized: SerializableDict, key: str = "conditions") -> List[Condition]:
    try:
        conditions_list_val = cast(list, serialized[key])
    except KeyError:
        raise

    processed_conditions: List[Condition] = []
    for item in conditions_list_val:
        item = cast(dict, item)
        processed_conditions.append(get_condition_from_serialized(item))
    return processed_conditions


def get_transaction_value(transaction: Transaction, path: str) -> Any:
    """Get a value from the transaction using a path.

    Args:
        transaction: The transaction.
        path: The path to the value e.g. "request.payload.model", "response.payload.choices", "data.user_id".

    Returns:
        The value at the path.

    Raises:
        ValueError: If the path is invalid or the value cannot be accessed.
    """
    vals = path.split(".")
    if len(vals) < 2:
        raise ValueError("Path must contain at least two components")

    x: Any = getattr(transaction, vals.pop(0))
    while vals:
        key = vals.pop(0)

        # Try dict-like access first (includes EventedDict)
        if hasattr(x, "__getitem__") and (isinstance(x, dict) or hasattr(x, "keys")):
            try:
                x = x[key]
                continue
            except (KeyError, TypeError):
                pass

        # Try attribute access
        if hasattr(x, key):
            x = getattr(x, key)
        else:
            # Try accessing as index for list-like objects
            try:
                x = x[int(key)]
            except (ValueError, TypeError, IndexError):
                raise AttributeError(f"Cannot access '{key}' on {type(x).__name__}")
    return x
