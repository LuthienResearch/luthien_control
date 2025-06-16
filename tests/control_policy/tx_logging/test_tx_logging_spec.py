from typing import Optional

import pytest
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.control_policy.tx_logging.tx_logging_spec import (
    LOGGING_SPEC_REGISTRY,
    LuthienLogData,
    TxLoggingSpec,
)
from luthien_control.core.tracked_context import TrackedContext  # For type hinting

# This can be removed as tests look comprehensive

# --- Tests for LuthienLogData --- #


def test_luthien_log_data_creation():
    """Test the creation and attribute access of LuthienLogData."""
    datatype = "test_type"
    data: SerializableDict = {"key": "value"}
    notes: SerializableDict = {"note": "test_note"}

    log_entry = LuthienLogData(datatype=datatype, data=data, notes=notes)

    assert log_entry.datatype == datatype
    assert log_entry.data == data
    assert log_entry.notes == notes


def test_luthien_log_data_optional_fields():
    """Test LuthienLogData with optional fields as None."""
    datatype = "minimal_type"
    log_entry = LuthienLogData(datatype=datatype, data=None, notes=None)

    assert log_entry.datatype == datatype
    assert log_entry.data is None
    assert log_entry.notes is None


# --- Helper: Dummy Concrete Spec for Testing Registration and Deserialization --- #


class DummyLoggingSpec(TxLoggingSpec):
    TYPE_NAME = "DummyLoggingSpec"

    def __init__(self, param: str = "default"):
        self.param = param

    def generate_log_data(self, context: "TrackedContext", notes: Optional[SerializableDict] = None) -> LuthienLogData:
        return LuthienLogData(datatype=self.TYPE_NAME, data={"param": self.param}, notes=notes)

    def serialize(self) -> SerializableDict:
        return SerializableDict({"type": self.TYPE_NAME, "param": self.param})

    @classmethod
    def _from_serialized_impl(cls, config: SerializableDict) -> "DummyLoggingSpec":
        param_value = config.get("param", "default_from_impl")
        if not isinstance(param_value, str):
            param_value = "default_from_impl"
        return cls(param=param_value)


# Explicitly register for tests if not automatically picked up (though __init_subclass__ should handle it)
# LOGGING_SPEC_REGISTRY[DummyLoggingSpec.TYPE_NAME] = DummyLoggingSpec

# --- Tests for TxLoggingSpec Registration --- #


def test_tx_logging_spec_registration():
    """Test that a concrete subclass of TxLoggingSpec gets registered."""
    # DummyLoggingSpec should have been registered via __init_subclass__
    assert DummyLoggingSpec.TYPE_NAME in LOGGING_SPEC_REGISTRY
    assert LOGGING_SPEC_REGISTRY[DummyLoggingSpec.TYPE_NAME] == DummyLoggingSpec


def test_tx_logging_spec_registration_warning_missing_type_name(capsys):
    """Test warning if TYPE_NAME is missing for a non-abstract spec."""

    class SpecWithoutTypeName(TxLoggingSpec):
        # No TYPE_NAME
        __is_abstract_type__ = False  # Explicitly mark as not an intermediate abstract class

        def generate_log_data(self, context, notes=None) -> LuthienLogData:
            return LuthienLogData(datatype="unknown", data=None, notes=notes)

        def serialize(self) -> SerializableDict:
            return SerializableDict({})

        @classmethod
        def _from_serialized_impl(cls, config: SerializableDict) -> "SpecWithoutTypeName":
            return cls()

    captured = capsys.readouterr()
    assert "Warning: TxLoggingSpec subclass SpecWithoutTypeName does not have a TYPE_NAME defined" in captured.out
    # Also verify it wasn't registered if TYPE_NAME is crucial and missing/empty
    # This depends on the strictness of the registration logic if TYPE_NAME is truly absent vs. empty
    # For now, we assume an empty/missing TYPE_NAME means no registration if a warning is issued.
    unnamed_specs = [name for name, cls_type in LOGGING_SPEC_REGISTRY.items() if cls_type == SpecWithoutTypeName]
    assert not unnamed_specs, "SpecWithoutTypeName should not be registered without a valid TYPE_NAME"


def test_tx_logging_spec_registration_abstract_no_warning(capsys):
    """Test that an abstract intermediate spec does not warn if TYPE_NAME is missing."""

    class AbstractIntermediateSpec(TxLoggingSpec):
        __is_abstract_type__ = True  # Mark as an intermediate abstract type

        # No TYPE_NAME needed here
        def generate_log_data(self, context, notes=None) -> LuthienLogData:
            return LuthienLogData(datatype="abstract", data=None, notes=notes)

        def serialize(self) -> SerializableDict:
            return SerializableDict({})

        @classmethod
        def _from_serialized_impl(cls, config: SerializableDict) -> "AbstractIntermediateSpec":
            return cls()

    captured = capsys.readouterr()
    assert (
        "Warning: TxLoggingSpec subclass AbstractIntermediateSpec does not have a TYPE_NAME defined" not in captured.out
    )


# --- Tests for TxLoggingSpec.from_serialized --- #


def test_from_serialized_valid_spec():
    """Test deserialization of a valid, registered spec type."""
    config: SerializableDict = {"type": DummyLoggingSpec.TYPE_NAME, "param": "test_param"}
    spec = TxLoggingSpec.from_serialized(config)
    assert isinstance(spec, DummyLoggingSpec)
    assert spec.param == "test_param"


def test_from_serialized_unknown_type():
    """Test deserialization with an unknown spec type."""
    config: SerializableDict = {"type": "NonExistentSpec"}
    with pytest.raises(ValueError, match="Unknown TxLoggingSpec type 'NonExistentSpec'"):
        TxLoggingSpec.from_serialized(config)


def test_from_serialized_missing_type_field():
    """Test deserialization with config missing the 'type' field."""
    config: SerializableDict = {"param": "some_value"}
    with pytest.raises(ValueError, match="configuration must include a 'type' field"):
        TxLoggingSpec.from_serialized(config)


def test_from_serialized_type_field_not_string():
    """Test deserialization with 'type' field not being a string."""
    config: SerializableDict = {"type": 123}
    with pytest.raises(ValueError, match="configuration must include a 'type' field as a string"):
        TxLoggingSpec.from_serialized(config)
