from typing import List, Type, cast

from luthien_control.control_policy.conditions.condition import Condition
from luthien_control.control_policy.conditions.registry import NAME_TO_CONDITION_CLASS
from luthien_control.control_policy.serialization import SerializableDict


def get_condition_class(name: str) -> Type[Condition]:
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
    for index, item in enumerate(conditions_list_val):
        item = cast(dict, item)
        processed_conditions.append(get_condition_from_serialized(item))
    return processed_conditions
