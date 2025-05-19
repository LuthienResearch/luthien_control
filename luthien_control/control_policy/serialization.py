# Serialization type definitions.

from dataclasses import dataclass
from typing import Any, Dict, List, TypeAlias, Union

# Define the base types that can be serialized
SerializablePrimitive = Union[str, float, int, bool]

# Define the recursive type for dictionaries
SerializableDict: TypeAlias = Dict[str, Union[SerializablePrimitive, List[Any], Dict[str, Any], None]]


# Define the type for serialized policies
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
