"""Defines logging specifications for TxLoggingPolicy."""

import abc
import logging
from typing import Any, NamedTuple, Optional, Type, TypeVar, cast

from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.tracked_context import TrackedContext

logger = logging.getLogger(__name__)

# Type variable for TxLoggingSpec classes
LoggingSpecT = TypeVar("LoggingSpecT", bound="TxLoggingSpec")


class LuthienLogData(NamedTuple):
    """Data structure for what a TxLoggingSpec should return."""

    datatype: str
    data: Optional[SerializableDict]
    notes: Optional[SerializableDict]


class TxLoggingSpec(abc.ABC):
    """Abstract Base Class for defining how to generate a log entry from a TransactionContext."""

    TYPE_NAME: str
    __is_abstract_type__: bool = False  # User-defined to mark intermediate abstract classes

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Registers subclasses in the LOGGING_SPEC_REGISTRY."""
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "TYPE_NAME") and cls.TYPE_NAME:
            if cls.TYPE_NAME in LOGGING_SPEC_REGISTRY:
                pass  # Allow re-registration
            LOGGING_SPEC_REGISTRY[cls.TYPE_NAME] = cls
        elif not getattr(cls, "__is_abstract_type__", False):
            print(
                f"Warning: TxLoggingSpec subclass {cls.__name__} does not have a TYPE_NAME defined or it is empty. "
                "It will not be registered."
            )

    @abc.abstractmethod
    def generate_log_data(self, context: "TrackedContext", notes: Optional[SerializableDict] = None) -> LuthienLogData:
        raise NotImplementedError

    @abc.abstractmethod
    def serialize(self) -> SerializableDict:
        raise NotImplementedError

    @classmethod
    def from_serialized(cls: Type[LoggingSpecT], config: SerializableDict) -> LoggingSpecT:
        spec_type_name = config.get("type")
        if not isinstance(spec_type_name, str):
            raise ValueError(
                f"TxLoggingSpec configuration must include a 'type' field as a string. "
                f"Got: {spec_type_name!r} (type: {type(spec_type_name).__name__})"
            )
        target_spec_class = LOGGING_SPEC_REGISTRY.get(spec_type_name)
        if not target_spec_class:
            raise ValueError(
                f"Unknown TxLoggingSpec type '{spec_type_name}'. Ensure it is registered in LOGGING_SPEC_REGISTRY."
                f" Available types: {list(LOGGING_SPEC_REGISTRY.keys())}"
            )
        return cast(LoggingSpecT, target_spec_class._from_serialized_impl(config))

    @classmethod
    @abc.abstractmethod
    def _from_serialized_impl(cls: Type[LoggingSpecT], config: SerializableDict) -> LoggingSpecT:
        raise NotImplementedError


# Registry for TxLoggingSpec types
# Define after TxLoggingSpec and LoggingSpecT are fully known
LOGGING_SPEC_REGISTRY: dict[str, Type[TxLoggingSpec]] = {}
