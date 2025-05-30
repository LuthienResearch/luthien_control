import logging
import uuid
from typing import Optional, cast
from unittest.mock import MagicMock, patch

# from fastapi import Response # Removed
import httpx
import pytest
from luthien_control.control_policy.add_api_key_header import AddApiKeyHeaderPolicy
from luthien_control.control_policy.client_api_key_auth import ClientApiKeyAuthPolicy
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import PolicyLoadError
from luthien_control.control_policy.noop_policy import NoopPolicy
from luthien_control.control_policy.serial_policy import SerialPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction_context import TransactionContext
from sqlalchemy.ext.asyncio import AsyncSession

# --- Test Fixtures and Helper Classes ---


class SimpleTestPolicy(ControlPolicy):
    """A simple test policy that tracks execution order and can set responses."""

    def __init__(
        self,
        name: str,
        sets_response: bool = False,
        should_raise: Optional[Exception] = None,
    ):
        self.name = name
        self.sets_response = sets_response
        self.should_raise = should_raise
        self.logger = logging.getLogger(self.__class__.__name__)

    async def apply(
        self,
        context: TransactionContext,
        container: DependencyContainer,
        session: AsyncSession,
    ) -> TransactionContext:
        self.logger.info(f"Applying {self.name}")
        call_order = context.data.setdefault("call_order", [])
        call_order.append(self.name)

        if self.should_raise:
            raise self.should_raise

        if self.sets_response:
            context.response = httpx.Response(status_code=299, content=f"Response from {self.name}".encode("utf-8"))
            self.logger.info(f"{self.name} setting response")

        self.logger.info(f"Finished {self.name}")
        return context

    def __repr__(self) -> str:
        return f"<{self.name}>"

    def serialize(self) -> SerializableDict:
        return {"name": self.name}

    @classmethod
    def from_serialized(cls, config: SerializableDict, **kwargs) -> "SimpleTestPolicy":
        name = config.get("name", "SimpleTestPolicy")
        return cls(name=str(name))


@pytest.fixture
def base_transaction_context() -> TransactionContext:
    """Provides a basic TransactionContext for tests."""
    return TransactionContext(transaction_id=uuid.uuid4())


# --- Test Cases ---


@pytest.mark.asyncio
async def test_serial_policy_applies_policies_sequentially(
    base_transaction_context,
    mock_db_session: AsyncSession,
    mock_container: DependencyContainer,
):
    """Test that policies are applied in the specified order."""
    policy1 = SimpleTestPolicy(name="Policy1")
    policy2 = SimpleTestPolicy(name="Policy2")
    serial = SerialPolicy(policies=[policy1, policy2], name="SequentialTest")

    # Pass mock session and container
    result_context = await serial.apply(
        base_transaction_context,
        container=mock_container,
        session=mock_db_session,
    )

    # Assertions
    assert result_context.data.get("call_order") == ["Policy1", "Policy2"]
    assert result_context is base_transaction_context  # Verify same context object is returned if not modified


@pytest.mark.asyncio
async def test_serial_policy_empty_list(
    base_transaction_context,
    caplog,
    mock_db_session: AsyncSession,
    mock_container: DependencyContainer,
):
    """Test that SerialPolicy handles an empty policy list gracefully."""
    serial = SerialPolicy(policies=[], name="EmptyTest")

    with caplog.at_level(logging.WARNING):
        result_context = await serial.apply(
            base_transaction_context,
            container=mock_container,
            session=mock_db_session,
        )

    assert result_context is base_transaction_context
    assert "Initializing SerialPolicy 'EmptyTest' with an empty policy list." in caplog.text


@pytest.mark.asyncio
async def test_serial_policy_propagates_exception(
    base_transaction_context,
    mock_db_session: AsyncSession,
    mock_container: DependencyContainer,
):
    """Test that an exception raised by a member policy propagates up."""

    class TestException(Exception):
        pass

    policy1 = SimpleTestPolicy(name="Policy1")
    policy2 = SimpleTestPolicy(name="Policy2", should_raise=TestException("Policy 2 failed!"))
    policy3 = SimpleTestPolicy(name="Policy3")
    serial = SerialPolicy(policies=[policy1, policy2, policy3], name="ExceptionTest")

    with pytest.raises(TestException, match="Policy 2 failed!"):
        await serial.apply(
            base_transaction_context,
            container=mock_container,
            session=mock_db_session,
        )

    # Check that policy1 was called, but policy3 was not
    assert base_transaction_context.data.get("call_order") == ["Policy1", "Policy2"]


@pytest.mark.asyncio
async def test_serial_policy_continues_on_response(
    base_transaction_context,
    mock_db_session: AsyncSession,
    mock_container: DependencyContainer,
):
    """Test that execution continues even if a member policy sets context.response."""
    policy1 = SimpleTestPolicy(name="Policy1")
    policy2 = SimpleTestPolicy(name="Policy2", sets_response=True)  # This policy sets a response
    policy3 = SimpleTestPolicy(name="Policy3")
    serial = SerialPolicy(policies=[policy1, policy2, policy3], name="ResponseTest")

    # Track the context object
    context_before_apply = base_transaction_context

    # Pass mock session and container
    result_context = await serial.apply(
        base_transaction_context,
        container=mock_container,
        session=mock_db_session,
    )

    # Ensure all policies were called
    assert result_context.data.get("call_order") == ["Policy1", "Policy2", "Policy3"]

    # The final result should be the original context object
    assert result_context is context_before_apply
    # Check that policy 2 did set the response on the context
    assert result_context.response is not None
    assert result_context.response.content == "Response from Policy2".encode("utf-8")


def test_serial_policy_repr():
    """Test the __repr__ method for clarity."""
    policy1 = SimpleTestPolicy(name="Policy1")
    policy2 = SimpleTestPolicy(name="Policy2")
    serial1 = SerialPolicy(policies=[policy1, policy2], name="AuthAndLog")
    serial2 = SerialPolicy(policies=[serial1, SimpleTestPolicy(name="Policy3")], name="MainFlow")

    assert repr(serial1) == "<AuthAndLog(policies=[Policy1 <SimpleTestPolicy>, Policy2 <SimpleTestPolicy>])>"
    assert repr(serial2) == "<MainFlow(policies=[AuthAndLog <SerialPolicy>, Policy3 <SimpleTestPolicy>])>"

    serial_default = SerialPolicy(policies=[policy1])
    assert repr(serial_default) == "<SerialPolicy(policies=[Policy1 <SimpleTestPolicy>])>"

    serial_empty = SerialPolicy(policies=[], name="Empty")
    assert repr(serial_empty) == "<Empty(policies=[])>"


def test_serial_policy_serialize_config():
    """Test the serialize_config method for SerialPolicy with nested structure."""

    member1 = NoopPolicy(name="NoopPolicy1")
    member2 = NoopPolicy(name="NoopPolicy2")

    serial = SerialPolicy(policies=[member1, member2], name="MySerial")

    expected_member1_config = member1.serialize()
    expected_member2_config = member2.serialize()

    expected_config = {
        "policies": [
            {"type": "NoopPolicy", "config": expected_member1_config},
            {"type": "NoopPolicy", "config": expected_member2_config},
        ]
    }

    assert serial.serialize() == expected_config


@pytest.mark.asyncio
async def test_serial_policy_serialization():
    """Test that SerialPolicy can be serialized and deserialized correctly, including nested policies."""
    # Arrange
    policy1 = ClientApiKeyAuthPolicy()
    policy2 = AddApiKeyHeaderPolicy(name="AddOpenAIKey")

    # Manually set policy_type for serialization registry lookup (usually handled by DB loading)
    # Ensure registry maps these types correctly

    original_serial_policy = SerialPolicy(policies=[policy1, policy2], name="TestSerial")

    # Act
    serialized_data = original_serial_policy.serialize()
    rehydrated_policy = SerialPolicy.from_serialized(serialized_data)

    assert isinstance(serialized_data, dict)
    assert "policies" in serialized_data
    policies_list = serialized_data["policies"]
    assert isinstance(policies_list, list)
    assert len(policies_list) == 2

    policy0_data = policies_list[0]
    assert isinstance(policy0_data, dict)
    assert policy0_data["type"] == "ClientApiKeyAuth"
    assert policy0_data["config"] == {
        "name": "ClientApiKeyAuthPolicy",
    }

    policy1_data = policies_list[1]
    assert isinstance(policy1_data, dict)
    assert policy1_data["type"] == "AddApiKeyHeader"
    assert policy1_data["config"] == {
        "name": "AddOpenAIKey",
    }

    assert isinstance(rehydrated_policy, SerialPolicy)
    assert len(rehydrated_policy.policies) == 2
    assert isinstance(rehydrated_policy.policies[0], ClientApiKeyAuthPolicy)
    assert isinstance(rehydrated_policy.policies[1], AddApiKeyHeaderPolicy)
    # Check the name is correct after rehydration
    assert rehydrated_policy.policies[1].name == "AddOpenAIKey"


def test_serial_policy_serialization_empty():
    """Test serialization with an empty list of policies."""
    # Arrange
    original_serial_policy = SerialPolicy(policies=[], name="EmptySerial")

    # Act
    serialized_data = original_serial_policy.serialize()
    rehydrated_policy = SerialPolicy.from_serialized(serialized_data)

    # Assert
    assert isinstance(serialized_data, dict)
    assert serialized_data == {"policies": []}
    assert isinstance(rehydrated_policy, SerialPolicy)
    assert len(rehydrated_policy.policies) == 0


def test_serial_policy_serialization_missing_policies_key():
    """Test deserialization when 'policies' key is missing from config."""
    # SerialPolicy.type is not used for this direct from_serialized call
    config_missing_policies = {"name": "TestMissing"}  # type: SerializableDict
    with pytest.raises(PolicyLoadError, match="SerialPolicy config missing 'policies' list \\(key not found\\)."):
        SerialPolicy.from_serialized(cast(SerializableDict, config_missing_policies))


def test_serial_policy_serialization_invalid_policy_item():
    """Test deserialization when a policy item in 'policies' is not a dict."""
    config_invalid_item: SerializableDict = {
        "name": "TestInvalidItem",
        "policies": ["not_a_dict"],  # Item in policies list is not a dict
    }
    with pytest.raises(
        PolicyLoadError, match="Item at index 0 in SerialPolicy 'policies' is not a dictionary\\. Got <class 'str'>"
    ):
        SerialPolicy.from_serialized(config_invalid_item)


@patch("luthien_control.control_policy.serial_policy.load_policy", new_callable=MagicMock)
def test_serial_policy_serialization_load_error(mock_load_policy):
    """Test that PolicyLoadError during load_policy is re-raised."""
    mock_load_policy.side_effect = PolicyLoadError("Failed to load sub-policy")
    config_load_error: SerializableDict = {
        "name": "TestLoadError",
        "policies": [{"type": "SubPolicy", "config": {}}],  # Dummy sub-policy structure
    }
    with pytest.raises(PolicyLoadError, match="Failed to load sub-policy"):
        SerialPolicy.from_serialized(config_load_error)


@patch("luthien_control.control_policy.serial_policy.load_policy", new_callable=MagicMock)
def test_serial_policy_serialization_unexpected_error(mock_load_policy):
    """Test that unexpected errors during load_policy are wrapped in PolicyLoadError."""
    mock_load_policy.side_effect = ValueError("Unexpected failure")
    config_unexpected_error: SerializableDict = {
        "name": "TestUnexpectedError",
        "policies": [{"type": "SubPolicy", "config": {}}],  # Dummy sub-policy structure
    }
    with pytest.raises(
        PolicyLoadError,
        match=(
            "Unexpected error loading member policy at index 0 \\(name: unknown\\) within SerialPolicy: "
            "Unexpected failure"
        ),
    ):
        SerialPolicy.from_serialized(config_unexpected_error)


def test_serial_policy_deserialize_invalid_policy_type():
    """Test that SerialPolicy raises ValueError if a policy type is not in the registry."""
    config_invalid_type: SerializableDict = {
        "name": "TestInvalidType",
        "policies": [{"type": "InvalidPolicyType", "config": {}}],
    }
    with pytest.raises(PolicyLoadError):
        SerialPolicy.from_serialized(config_invalid_type)
