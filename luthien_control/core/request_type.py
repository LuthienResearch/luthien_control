"""Request type enum for Transaction objects."""

from enum import Enum


class RequestType(str, Enum):
    """Enum for different request types in a Transaction."""

    OPENAI_CHAT = "openai_chat"
    RAW_PASSTHROUGH = "raw_passthrough"
