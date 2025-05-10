# Serialization type definitions.

from dataclasses import dataclass
from typing import Dict, Union

SerializableType = Union[str, float, int, bool, "SerializableDict"]

SerializableDict = Dict[str, SerializableType]


@dataclass
class SerializedPolicy:
    """Represents the serialized form of a ControlPolicy.

    This structure is used to store and transfer policy configurations.
    The 'type' field identifies the specific policy class, and the 'config'
    field contains the parameters needed to reconstruct that policy instance.

    Attributes:
        type (str): The registered name of the policy type (e.g., "AddApiKeyHeader").
        config (SerializableDict): A dictionary containing the configuration
                                   parameters for the policy instance.
    """

    type: str
    config: SerializableDict
