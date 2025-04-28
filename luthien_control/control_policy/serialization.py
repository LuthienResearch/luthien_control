"""Serialization type definitions."""

from dataclasses import dataclass
from typing import Dict, Union

SerializableType = Union[str, float, int, bool, "SerializableDict"]

SerializableDict = Dict[str, SerializableType]


@dataclass
class SerializedPolicy:
    type: str
    config: SerializableDict
