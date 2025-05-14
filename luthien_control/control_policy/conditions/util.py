from typing import List, Type

from luthien_control.control_policy.conditions.condition import Condition
from luthien_control.control_policy.conditions.registry import NAME_TO_CONDITION_CLASS
from luthien_control.control_policy.serialization import SerializableDict


def get_condition_class(name: str) -> Type[Condition]:
    return NAME_TO_CONDITION_CLASS[name]


def get_condition_class_from_serialized(serialized: SerializableDict) -> Type[Condition]:
    return get_condition_class(serialized["type"])


def get_condition_from_serialized(serialized: SerializableDict) -> Condition:
    return get_condition_class_from_serialized(serialized).from_serialized(serialized)


def get_conditions_from_serialized(serialized: SerializableDict, key: str = "conditions") -> List[Condition]:
    return [get_condition_from_serialized(cond) for cond in serialized[key]]
