from typing import Dict, TypeVar, Union

T = TypeVar("T", bound="SerializableDict")

SerializableType = Union[str, float, int, "SerializableDict"]

SerializableDict = Dict[str, SerializableType]

class PolicyClassNames:
    """Class names for control policies."""

    ADD_API_KEY_HEADER = "AddApiKeyHeaderPolicy"
    SEND_BACKEND_REQUEST = "SendBackendRequestPolicy"
    REQUEST_LOGGING = "RequestLoggingPolicy"
    