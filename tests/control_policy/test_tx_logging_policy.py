import logging  # For caplog
from datetime import datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock, MagicMock  # For mocking async session and spec methods

import pytest
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.control_policy.tx_logging.tx_logging_spec import (
    LOGGING_SPEC_REGISTRY,
    LuthienLogData,
    TxLoggingSpec,
)
from luthien_control.control_policy.tx_logging_policy import TxLoggingPolicy
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction_context import TransactionContext
from luthien_control.db.sqlmodel_models import LuthienLog

# --- Test Fixtures and Mocks ---


class MockTxLoggingSpec(TxLoggingSpec):
    """A mock TxLoggingSpec for testing purposes."""

    TYPE_NAME = "MockTxLoggingSpec"

    def __init__(
        self,
        name: str = "mock_spec",
        data_to_return: Optional[LuthienLogData] = None,
        raise_on_generate: Optional[Exception] = None,
    ):
        self.name = name
        self.data_to_return = data_to_return
        self.raise_on_generate = raise_on_generate
        self.generate_log_data_called_with = None
        self.serialize_called = False

    def generate_log_data(
        self, context: "TransactionContext", notes: Optional[SerializableDict] = None
    ) -> Optional[LuthienLogData]:
        self.generate_log_data_called_with = {"context": context, "notes": notes}
        if self.raise_on_generate:
            raise self.raise_on_generate
        return self.data_to_return

    def serialize(self) -> SerializableDict:
        self.serialize_called = True
        return SerializableDict({"type": self.TYPE_NAME, "name": self.name})

    @classmethod
    def _from_serialized_impl(cls, config: SerializableDict) -> "MockTxLoggingSpec":
        name_value = config.get("name", "deserialized_mock")
        if not isinstance(name_value, str):
            name_value = "deserialized_mock"
        return cls(name=name_value)


# Ensure the mock spec is registered for deserialization tests
LOGGING_SPEC_REGISTRY[MockTxLoggingSpec.TYPE_NAME] = MockTxLoggingSpec


@pytest.fixture
def mock_spec() -> MockTxLoggingSpec:
    return MockTxLoggingSpec()


@pytest.fixture
def mock_transaction_context() -> TransactionContext:
    mock_context = MagicMock(spec=TransactionContext)
    mock_context.transaction_id = "test-tx-123"
    mock_context.request = None  # Can be set in specific tests if needed
    mock_context.response = None  # Can be set in specific tests if needed
    mock_context.data = {}
    return mock_context


@pytest.fixture
def mock_dependency_container() -> DependencyContainer:
    return MagicMock(spec=DependencyContainer)


@pytest.fixture
def mock_async_session() -> AsyncMock:  # Use AsyncMock for async methods
    session = AsyncMock()
    session.add = MagicMock()  # session.add is synchronous
    return session


# --- Tests for TxLoggingPolicy ---


def test_tx_logging_policy_init(mock_spec: MockTxLoggingSpec):
    """Test policy initialization."""
    policy = TxLoggingPolicy(spec=mock_spec, name="MyLoggingPolicy")
    assert policy.name == "MyLoggingPolicy"
    assert policy.spec == mock_spec

    policy_default_name = TxLoggingPolicy(spec=mock_spec)
    assert policy_default_name.name == "TxLoggingPolicy"


async def test_log_database_entry(mock_async_session: AsyncMock):
    """Test the _log_database_entry helper method."""
    policy = TxLoggingPolicy(spec=MockTxLoggingSpec())  # Spec doesn't matter here
    tx_id = "tx-log-entry-test"
    dt = datetime.now(timezone.utc)
    log_data = LuthienLogData(
        datatype="test_dt", data=SerializableDict({"key": "val"}), notes=SerializableDict({"n": "v"})
    )

    await policy._log_database_entry(mock_async_session, tx_id, dt, log_data)

    mock_async_session.add.assert_called_once()
    added_log_entry = mock_async_session.add.call_args[0][0]
    assert isinstance(added_log_entry, LuthienLog)
    assert added_log_entry.transaction_id == tx_id
    assert added_log_entry.datetime == dt
    assert added_log_entry.datatype == "test_dt"
    assert added_log_entry.data == {"key": "val"}
    assert added_log_entry.notes == {"n": "v"}


async def test_apply_successful_logging(
    mock_spec: MockTxLoggingSpec,
    mock_transaction_context: TransactionContext,
    mock_dependency_container: DependencyContainer,
    mock_async_session: AsyncMock,
    caplog: pytest.LogCaptureFixture,
):
    """Test apply method with successful logging."""
    log_data_to_return = LuthienLogData(datatype="dummy_data", data=SerializableDict({"field": "value"}), notes=None)
    mock_spec.data_to_return = log_data_to_return

    policy = TxLoggingPolicy(spec=mock_spec)

    with caplog.at_level(logging.INFO):
        returned_context = await policy.apply(mock_transaction_context, mock_dependency_container, mock_async_session)

    assert returned_context == mock_transaction_context  # Context should be returned
    assert mock_spec.generate_log_data_called_with is not None
    assert mock_spec.generate_log_data_called_with["context"] == mock_transaction_context
    mock_async_session.add.assert_called_once()
    added_log_entry = mock_async_session.add.call_args[0][0]
    assert added_log_entry.datatype == "dummy_data"
    assert f"Logged data for transaction {mock_transaction_context.transaction_id}" in caplog.text
    assert f"via spec type {mock_spec.TYPE_NAME}" in caplog.text
    assert f"datatype {log_data_to_return.datatype}" in caplog.text


async def test_apply_spec_returns_none(
    mock_spec: MockTxLoggingSpec,
    mock_transaction_context: TransactionContext,
    mock_dependency_container: DependencyContainer,
    mock_async_session: AsyncMock,
):
    """Test apply when the spec returns no log data."""
    mock_spec.data_to_return = None  # Spec generates nothing to log
    policy = TxLoggingPolicy(spec=mock_spec)

    returned_context = await policy.apply(mock_transaction_context, mock_dependency_container, mock_async_session)

    assert returned_context == mock_transaction_context
    assert mock_spec.generate_log_data_called_with is not None
    assert mock_spec.generate_log_data_called_with["context"] == mock_transaction_context
    mock_async_session.add.assert_not_called()


async def test_apply_spec_generate_raises_exception(
    mock_spec: MockTxLoggingSpec,
    mock_transaction_context: TransactionContext,
    mock_dependency_container: DependencyContainer,
    mock_async_session: AsyncMock,
    caplog: pytest.LogCaptureFixture,
):
    """Test apply when spec.generate_log_data raises an exception."""
    test_exception = ValueError("Spec generation failed!")
    mock_spec.raise_on_generate = test_exception
    policy = TxLoggingPolicy(spec=mock_spec)

    with caplog.at_level(logging.ERROR):
        returned_context = await policy.apply(mock_transaction_context, mock_dependency_container, mock_async_session)

    assert returned_context == mock_transaction_context
    mock_async_session.add.assert_not_called()
    assert f"Error during logging for transaction {mock_transaction_context.transaction_id}" in caplog.text
    assert f"with spec {mock_spec.TYPE_NAME}" in caplog.text
    assert f"(policy: {policy.name})" in caplog.text
    assert str(test_exception) in caplog.text


async def test_apply_log_database_entry_raises_exception(
    mock_spec: MockTxLoggingSpec,
    mock_transaction_context: TransactionContext,
    mock_dependency_container: DependencyContainer,
    mock_async_session: AsyncMock,
    caplog: pytest.LogCaptureFixture,
):
    """Test apply when _log_database_entry (e.g., session.add) raises an exception."""
    log_data_to_return = LuthienLogData(datatype="db_error_test", data=SerializableDict({}), notes=None)
    mock_spec.data_to_return = log_data_to_return

    db_error = RuntimeError("Database commit failed")
    mock_async_session.add.side_effect = db_error  # Simulate error on session.add

    policy = TxLoggingPolicy(spec=mock_spec)

    with caplog.at_level(logging.ERROR):
        returned_context = await policy.apply(mock_transaction_context, mock_dependency_container, mock_async_session)

    assert returned_context == mock_transaction_context
    mock_async_session.add.assert_called_once()  # It was called
    assert f"Error during logging for transaction {mock_transaction_context.transaction_id}" in caplog.text
    assert str(db_error) in caplog.text  # Ensure the original exception is logged


def test_tx_logging_policy_serialize(mock_spec: MockTxLoggingSpec):
    """Test policy serialization."""
    policy = TxLoggingPolicy(spec=mock_spec, name="SerializeMe")
    serialized = policy.serialize()

    assert mock_spec.serialize_called
    assert isinstance(serialized, dict)
    assert serialized["type"] == TxLoggingPolicy.TYPE_NAME
    assert serialized["name"] == "SerializeMe"
    assert serialized["spec"] == {"type": MockTxLoggingSpec.TYPE_NAME, "name": "mock_spec"}


def test_tx_logging_policy_from_serialized_valid():
    """Test deserialization with valid config."""
    config = SerializableDict(
        {
            "type": TxLoggingPolicy.TYPE_NAME,
            "name": "MyDeserializedPolicy",
            "spec": {"type": MockTxLoggingSpec.TYPE_NAME, "name": "custom_mock_spec_name"},
        }
    )
    policy = TxLoggingPolicy.from_serialized(config)

    assert isinstance(policy, TxLoggingPolicy)
    assert policy.name == "MyDeserializedPolicy"
    assert isinstance(policy.spec, MockTxLoggingSpec)
    assert policy.spec.name == "custom_mock_spec_name"


def test_tx_logging_policy_from_serialized_default_name():
    """Test deserialization with default policy name."""
    config = SerializableDict(
        {
            "type": TxLoggingPolicy.TYPE_NAME,
            # No name field
            "spec": {"type": MockTxLoggingSpec.TYPE_NAME},  # Relies on MockTxLoggingSpec default param
        }
    )
    policy = TxLoggingPolicy.from_serialized(config)
    assert policy.name == TxLoggingPolicy.TYPE_NAME  # Should default to class's TYPE_NAME
    assert isinstance(policy.spec, MockTxLoggingSpec)
    assert policy.spec.name == "deserialized_mock"  # Default from MockTxLoggingSpec._from_serialized_impl


def test_tx_logging_policy_from_serialized_invalid_name_type():
    """Test deserialization with 'name' field of invalid type."""
    config = SerializableDict(
        {
            "type": TxLoggingPolicy.TYPE_NAME,
            "name": 12345,  # Invalid type for name
            "spec": {"type": MockTxLoggingSpec.TYPE_NAME},
        }
    )
    # The current implementation falls back to TYPE_NAME if name is not str or None.
    # It does not raise an error, which might be acceptable.
    policy = TxLoggingPolicy.from_serialized(config)
    assert policy.name == TxLoggingPolicy.TYPE_NAME


@pytest.mark.parametrize(
    "bad_spec_config, error_message_match",
    [
        (None, "TxLoggingPolicy config missing 'spec' dictionary."),
        ("not_a_dict", "TxLoggingPolicy config missing 'spec' dictionary."),
        ({}, "Error deserializing spec"),  # No 'type' in spec
        ({"type": "UnknownSpecType"}, "Error deserializing spec.*Unknown TxLoggingSpec type 'UnknownSpecType'"),
    ],
)
def test_tx_logging_policy_from_serialized_bad_spec(bad_spec_config, error_message_match):
    """Test deserialization with various invalid spec configurations."""
    config = SerializableDict({"type": TxLoggingPolicy.TYPE_NAME, "name": "BadSpecPolicy", "spec": bad_spec_config})
    with pytest.raises(ValueError, match=error_message_match):
        TxLoggingPolicy.from_serialized(config)
