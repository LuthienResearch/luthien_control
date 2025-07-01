# Serialization type definitions.

from dataclasses import dataclass
from typing import Any, List, TypeAlias, TypeVar, Union

from pydantic import BaseModel, TypeAdapter

# Define the base types that can be serialized
SerializablePrimitive = Union[str, float, int, bool]

# Define the recursive type for dictionaries
SerializableDict: TypeAlias = dict[str, Union[SerializablePrimitive, List[Any], dict[str, Any], None]]

SerializableDictAdapter = TypeAdapter(SerializableDict)


def safe_model_dump(model: BaseModel) -> SerializableDict:
    """Safely dump a Pydantic model through SerializableDict validation."""
    data = model.model_dump(mode="python", by_alias=True)
    return SerializableDictAdapter.validate_python(data)


T = TypeVar("T", bound=BaseModel)


def safe_model_validate(model_class: type[T], data: SerializableDict) -> T:
    """Safely validate data through SerializableDict before creating model."""
    validated_data = SerializableDictAdapter.validate_python(data)
    return model_class.model_validate(validated_data, from_attributes=True)


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
