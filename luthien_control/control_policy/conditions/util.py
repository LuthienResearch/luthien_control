from typing import List, Type

from luthien_control.control_policy.conditions.condition import Condition
from luthien_control.control_policy.conditions.registry import NAME_TO_CONDITION_CLASS
from luthien_control.control_policy.serialization import SerializableDict


def get_condition_class(name: str) -> Type[Condition]:
    return NAME_TO_CONDITION_CLASS[name]


def get_condition_class_from_serialized(serialized: SerializableDict) -> Type[Condition]:
    condition_type_name = serialized.get("type")
    if not isinstance(condition_type_name, str):
        raise TypeError(
            f"Condition 'type' in serialized config must be a string. "
            f"Got: {condition_type_name!r} (type: {type(condition_type_name).__name__})"
        )
    return get_condition_class(condition_type_name)


def get_condition_from_serialized(serialized: SerializableDict) -> Condition:
    return get_condition_class_from_serialized(serialized).from_serialized(serialized)


def get_conditions_from_serialized(serialized: SerializableDict, key: str = "conditions") -> List[Condition]:
    try:
        conditions_list_val = serialized[key]
    except KeyError:
        raise

    if not isinstance(conditions_list_val, list):
        raise TypeError(
            f"Expected '{key}' in serialized config to be a list of condition configurations. "
            f"Got: {conditions_list_val!r} (type: {type(conditions_list_val).__name__})"
        )

    processed_conditions: List[Condition] = []
    for index, item in enumerate(conditions_list_val):
        if not isinstance(item, dict):
            raise TypeError(
                f"Item at index {index} in '{key}' list is not a dictionary (expected a condition configuration). "
                f"Got: {item!r} (type: {type(item).__name__})"
            )
        processed_conditions.append(get_condition_from_serialized(item))
    return processed_conditions
