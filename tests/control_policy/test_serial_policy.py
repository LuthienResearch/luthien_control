import logging
from typing import Any, Optional, cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from luthien_control.api.openai_chat_completions.datatypes import Choice, Message, Usage
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import PolicyLoadError
from luthien_control.control_policy.noop_policy import NoopPolicy
from luthien_control.control_policy.serial_policy import SerialPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.request import Request
from luthien_control.core.response import Response
from luthien_control.core.transaction import Transaction
from psygnal.containers import EventedDict, EventedList
from sqlalchemy.ext.asyncio import AsyncSession

# --- Test Fixtures and Helper Classes ---


class MockSimplePolicy(ControlPolicy):
    """A simple mock policy for testing."""

    modifies_data: bool = False

    def __init__(self, side_effect: Any = None, modifies_data: bool = False, name: Optional[str] = None, **kwargs):
        super().__init__(name=name or self.__class__.__name__, modifies_data=modifies_data, **kwargs)
        self.apply_mock = AsyncMock(side_effect=side_effect)
        self.logger = logging.getLogger(self.__class__.__name__)

    @classmethod
    def get_policy_type_name(cls) -> str:
        """Override to avoid registry lookup for test class."""
        return "MockSimplePolicy"

    class Config:
        extra = "allow"  # Allow extra fields like apply_mock

    async def apply(
        self,
        transaction: Transaction,
        container: DependencyContainer,
        session: AsyncSession,
    ) -> Transaction:
        self.logger.info(f"Applying {self.name}")

        # Track call order in transaction data
        if transaction.data is None:
            transaction.data = EventedDict()

        call_order = transaction.data.get("call_order", [])
        if not call_order:
            transaction.data["call_order"] = []
            call_order = transaction.data["call_order"]
        call_order.append(self.name)

        if self.modifies_data:
            transaction.data[f"modified_by_{self.name}"] = True
            self.logger.info(f"{self.name} modifying data")

        await self.apply_mock(transaction, container=container, session=session)
        self.logger.info(f"Finished {self.name}")
        return transaction

    def __repr__(self) -> str:
        return f"<{self.name}>"

    def get_policy_config(self) -> SerializableDict:
        return cast(SerializableDict, {"name": self.name})

    @classmethod
    def from_serialized(cls, config: SerializableDict, **kwargs) -> "MockSimplePolicy":
        """Dummy implementation to satisfy abstract base class."""
        name = config.get("name", cls.__name__)
        return cls(name=str(name))


@pytest.fixture
def sample_transaction() -> Transaction:
    """Provides a Transaction for testing."""
    request = Request(
        payload=OpenAIChatCompletionsRequest(
            model="gpt-4",
            messages=EventedList([Message(role="user", content="Hello, world!")]),
        ),
        api_endpoint="https://api.openai.com/v1/chat/completions",
        api_key="test_key",
    )

    response = Response(
        payload=OpenAIChatCompletionsResponse(
            id="chatcmpl-123",
            object="chat.completion",
            created=1677652288,
            model="gpt-4",
            choices=EventedList(
                [Choice(index=0, message=Message(role="assistant", content="Hello there!"), finish_reason="stop")]
            ),
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
    )

    transaction_data = EventedDict(
        {
            "test_key": "test_value",
        }
    )

    return Transaction(request=request, response=response, data=transaction_data)


@pytest.fixture
def mock_container() -> MagicMock:
    """Provides a mock dependency container."""
    return MagicMock()


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Provides a mock database session."""
    return AsyncMock()


# --- Test Cases ---


@pytest.mark.asyncio
async def test_serial_policy_applies_policies_sequentially(
    sample_transaction,
    mock_db_session: AsyncSession,
    mock_container: DependencyContainer,
):
    """Test that policies are applied in the specified order."""
    policy1 = MockSimplePolicy(name="Policy1")
    policy2 = MockSimplePolicy(name="Policy2")
    serial = SerialPolicy(policies=[policy1, policy2], name="SequentialTest")

    # Pass mock session and container
    result_transaction = await serial.apply(
        sample_transaction,
        container=mock_container,
        session=mock_db_session,
    )

    # Assertions
    assert result_transaction.data is not None
    assert result_transaction.data["call_order"] == ["Policy1", "Policy2"]
    # Ensure the mock policies were called with the correct context
    assert policy1.apply_mock.call_args[0][0] == sample_transaction
    # The transaction passed to policy2 should be the result of policy1
    assert policy2.apply_mock.call_args[0][0] == sample_transaction
    # Check session and container were passed
    policy1.apply_mock.assert_awaited_once_with(sample_transaction, container=mock_container, session=mock_db_session)
    policy2.apply_mock.assert_awaited_once_with(sample_transaction, container=mock_container, session=mock_db_session)
    assert result_transaction is sample_transaction  # Verify same transaction object is returned


@pytest.mark.asyncio
async def test_serial_policy_empty_list(
    sample_transaction,
    caplog,
    mock_db_session: AsyncSession,
    mock_container: DependencyContainer,
):
    """Test that SerialPolicy handles an empty policy list gracefully."""
    serial = SerialPolicy(policies=[], name="EmptyTest")

    with caplog.at_level(logging.WARNING):
        result_transaction = await serial.apply(
            sample_transaction,
            container=mock_container,
            session=mock_db_session,
        )

    assert result_transaction is sample_transaction
    assert "Initializing SerialPolicy 'EmptyTest' with an empty policy list." in caplog.text


@pytest.mark.asyncio
async def test_serial_policy_propagates_exception(
    sample_transaction,
    mock_db_session: AsyncSession,
    mock_container: DependencyContainer,
):
    """Test that SerialPolicy propagates exceptions from member policies."""
    test_exception = ValueError("Test exception from policy")
    policy1 = MockSimplePolicy(name="Policy1")
    policy2 = MockSimplePolicy(side_effect=test_exception, name="Policy2")
    policy3 = MockSimplePolicy(name="Policy3")  # Should not be called
    serial = SerialPolicy(policies=[policy1, policy2, policy3], name="ExceptionTest")

    with pytest.raises(ValueError, match="Test exception from policy"):
        await serial.apply(
            sample_transaction,
            container=mock_container,
            session=mock_db_session,
        )

    # Verify policy1 was called but policy3 was not
    policy1.apply_mock.assert_awaited_once()
    policy2.apply_mock.assert_awaited_once()
    policy3.apply_mock.assert_not_awaited()

    # Verify call order reflects what actually happened
    assert sample_transaction.data["call_order"] == ["Policy1", "Policy2"]


@pytest.mark.asyncio
async def test_serial_policy_with_real_policies(
    sample_transaction,
    mock_db_session: AsyncSession,
    mock_container: DependencyContainer,
):
    """Test SerialPolicy with real NoopPolicy instances."""
    policy1 = NoopPolicy(name="Noop1")
    policy2 = NoopPolicy(name="Noop2")
    serial = SerialPolicy(policies=[policy1, policy2], name="RealPolicyTest")

    result_transaction = await serial.apply(
        sample_transaction,
        container=mock_container,
        session=mock_db_session,
    )

    assert result_transaction is sample_transaction
    # NoopPolicies don't modify the transaction


def test_serial_policy_repr():
    """Test SerialPolicy string representation."""
    policy1 = NoopPolicy(name="Noop1")
    policy2 = NoopPolicy(name="Noop2")
    serial = SerialPolicy(policies=[policy1, policy2], name="ReprTest")

    repr_str = repr(serial)
    assert "ReprTest" in repr_str
    assert "Noop1" in repr_str
    assert "Noop2" in repr_str
    assert "NoopPolicy" in repr_str


def test_serial_policy_serialize():
    """Test SerialPolicy serialization."""
    policy1 = NoopPolicy(name="Noop1")
    policy2 = NoopPolicy(name="Noop2")
    serial = SerialPolicy(policies=[policy1, policy2], name="SerializeTest")

    serialized = serial.serialize()

    assert "type" in serialized
    assert serialized["type"] == "SerialPolicy"
    assert "name" in serialized
    assert serialized["name"] == "SerializeTest"
    assert "policies" in serialized
    policies_list = serialized["policies"]
    assert isinstance(policies_list, list)
    assert len(policies_list) == 2

    # Check first policy
    first_policy = policies_list[0]
    assert isinstance(first_policy, dict)
    assert first_policy["type"] == "NoopPolicy"
    assert first_policy["name"] == "Noop1"

    # Check second policy
    second_policy = policies_list[1]
    assert isinstance(second_policy, dict)
    assert second_policy["type"] == "NoopPolicy"
    assert second_policy["name"] == "Noop2"


def test_serial_policy_serialize_unknown_policy_type():
    """Test SerialPolicy serialization with mock policy type."""
    # Create a policy that's not in the registry but has get_policy_type_name
    unknown_policy = MockSimplePolicy(name="Unknown")
    serial = SerialPolicy(policies=[unknown_policy], name="UnknownTest")

    serialized = serial.serialize()
    assert serialized["type"] == "SerialPolicy"
    assert "policies" in serialized


def test_serial_policy_from_serialized_valid():
    """Test SerialPolicy deserialization with valid config."""
    config = cast(
        SerializableDict,
        {
            "name": "DeserializedSerial",
            "policies": [
                {"name": "Noop1", "type": "NoopPolicy"},
                {"name": "Noop2", "type": "NoopPolicy"},
            ],
        },
    )

    serial = SerialPolicy.from_serialized(config)

    assert serial.name == "DeserializedSerial"
    assert len(serial.policies) == 2
    assert isinstance(serial.policies[0], NoopPolicy)
    assert isinstance(serial.policies[1], NoopPolicy)
    assert serial.policies[0].name == "Noop1"
    assert serial.policies[1].name == "Noop2"


def test_serial_policy_from_serialized_missing_policies():
    """Test SerialPolicy deserialization with missing policies key."""
    config = cast(SerializableDict, {"name": "MissingPolicies"})

    with pytest.raises(PolicyLoadError, match="SerialPolicy config missing 'policies' list"):
        SerialPolicy.from_serialized(config)


def test_serial_policy_from_serialized_policies_not_iterable():
    """Test SerialPolicy deserialization with non-iterable policies."""
    config = cast(SerializableDict, {"policies": 123})  # Use a non-iterable type

    with pytest.raises(PolicyLoadError, match="SerialPolicy 'policies' must be an iterable"):
        SerialPolicy.from_serialized(config)


def test_serial_policy_from_serialized_policy_not_dict():
    """Test SerialPolicy deserialization with non-dict policy."""
    config = cast(SerializableDict, {"policies": ["not_a_dict"]})

    with pytest.raises(PolicyLoadError, match="Item at index 0 in SerialPolicy 'policies' is not a dictionary"):
        SerialPolicy.from_serialized(config)


def test_serial_policy_from_serialized_config_not_dict():
    """Test SerialPolicy deserialization with non-dict member_config."""
    config = cast(SerializableDict, {"policies": [{"type": "NoopPolicy", "config": "not_a_dict"}]})

    with pytest.raises(
        PolicyLoadError, match="Member policy at index 0 must have a 'config' field as dict. Got: <class 'str'>"
    ):
        SerialPolicy.from_serialized(config)


def test_serial_policy_from_serialized_missing_type():
    """Test SerialPolicy deserialization with missing policy type."""
    config = cast(SerializableDict, {"policies": [{"name": "test"}]})

    with pytest.raises(
        PolicyLoadError,
        match="Failed to load member policy at index 0.*Member policy at index 0 must have a 'type' field as string",
    ):
        SerialPolicy.from_serialized(config)


def test_serial_policy_from_serialized_missing_config():
    """Test SerialPolicy deserialization with missing policy config."""
    config = cast(SerializableDict, {"policies": [{"type": "NoopPolicy"}]})

    # This should pass now since config is no longer required as a separate field
    serial = SerialPolicy.from_serialized(config)
    assert len(serial.policies) == 1
    assert isinstance(serial.policies[0], NoopPolicy)


def test_serial_policy_from_serialized_unknown_policy_type():
    """Test SerialPolicy deserialization with unknown policy type."""
    config = cast(SerializableDict, {"policies": [{"type": "UnknownPolicy", "name": "test"}]})

    with pytest.raises(
        PolicyLoadError, match="Failed to load member policy at index 0.*Unknown policy type: 'UnknownPolicy'"
    ):
        SerialPolicy.from_serialized(config)


def test_serial_policy_from_serialized_unexpected_error():
    """Test SerialPolicy deserialization with unexpected error during policy loading."""
    # Create a policy config that will cause an unexpected error during loading
    # We'll simulate this by mocking the ControlPolicy.from_serialized method to raise an unexpected exception
    from unittest.mock import patch

    config = cast(SerializableDict, {"policies": [{"name": "test", "type": "NoopPolicy"}]})

    # SerialPolicy.from_serialized now uses load_policy which handles the creation
    # We need to patch the load_policy function where it's imported from
    with patch("luthien_control.control_policy.loader.load_policy") as mock_load:
        mock_load.side_effect = RuntimeError("Simulated unexpected error")

        with pytest.raises(PolicyLoadError, match="Unexpected error loading member policy at index 0"):
            SerialPolicy.from_serialized(config)


def test_serial_policy_from_serialized_no_name():
    """Test SerialPolicy deserialization without name."""
    config = cast(SerializableDict, {"policies": []})

    serial = SerialPolicy.from_serialized(config)
    assert serial.name == "SerialPolicy"


def test_serial_policy_from_serialized_non_string_name():
    """Test SerialPolicy deserialization with non-string name raises ValidationError."""
    from pydantic import ValidationError

    config = cast(SerializableDict, {"name": 12345, "policies": []})

    with pytest.raises(ValidationError):  # Pydantic will raise ValidationError for invalid types
        SerialPolicy.from_serialized(config)


def test_serial_policy_round_trip():
    """Test SerialPolicy serialization and deserialization round trip."""
    policy1 = NoopPolicy(name="Noop1")
    policy2 = NoopPolicy(name="Noop2")
    original = SerialPolicy(policies=[policy1, policy2], name="RoundTrip")

    # Serialize
    serialized = original.serialize()

    # Deserialize
    restored = SerialPolicy.from_serialized(serialized)

    # Verify
    assert restored.name == original.name
    assert len(restored.policies) == len(original.policies)
    assert restored.policies[0].name == original.policies[0].name
    assert restored.policies[1].name == original.policies[1].name


def test_compound_policy_alias():
    """Test that CompoundPolicy is an alias for SerialPolicy."""
    from luthien_control.control_policy.serial_policy import CompoundPolicy

    assert CompoundPolicy is SerialPolicy


def test_policy_load_error_in_from_serialized():
    """Test that PolicyLoadError is re-raised with additional context."""
    from unittest.mock import patch

    # Create a policy config that will cause a PolicyLoadError during loading
    bad_config = {
        "type": "serial",
        "name": "test_serial",
        "policies": [
            {
                "type": "nonexistent_policy_type",  # This should cause a PolicyLoadError
                "name": "bad_policy",
            }
        ],
    }

    # Mock the ControlPolicy.from_serialized to raise PolicyLoadError
    with patch("luthien_control.control_policy.control_policy.ControlPolicy.from_serialized") as mock_from_serialized:
        mock_from_serialized.side_effect = PolicyLoadError("Test error")

        with pytest.raises(PolicyLoadError, match="Failed to load member policy at index 0"):
            SerialPolicy.from_serialized(bad_config)
