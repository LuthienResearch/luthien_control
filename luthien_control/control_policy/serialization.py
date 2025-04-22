from typing import Dict, TypeVar, Union

T = TypeVar("T", bound="SerializableDict")

SerializableType = Union[str, float, int, "SerializableDict"]

SerializableDict = Dict[str, SerializableType]
