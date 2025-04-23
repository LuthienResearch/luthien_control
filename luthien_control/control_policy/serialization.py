"""Serialization type definitions."""

from typing import Dict, Union

SerializableType = Union[str, float, int, bool, "SerializableDict"]

SerializableDict = Dict[str, SerializableType]
