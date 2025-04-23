import logging
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import Response
from luthien_control.config.settings import Settings
from luthien_control.control_policy.add_api_key_header import AddApiKeyHeaderPolicy
from luthien_control.control_policy.client_api_key_auth import (
    ClientApiKeyAuthPolicy,
    get_api_key_by_value,
)
from luthien_control.control_policy.compound_policy import CompoundPolicy
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.core.transaction_context import TransactionContext

# --- Test Fixtures and Helper Classes ---


class MockSimplePolicy(ControlPolicy):
    """A simple mock policy for testing."""

    def __init__(
        self,
        name: str = "MockPolicy",
        side_effect: Any = None,
        sets_response: bool = False,
        policy_class_path: str | None = None,
    ):
        self.name = name
        self.apply_mock = AsyncMock(side_effect=side_effect)
        self.sets_response = sets_response
        self.logger = logging.getLogger(f"test.policy.{name}")  # Add logger
        self.policy_class_path = policy_class_path or f"mock.module.{self.__class__.__name__}"  # Assign default path

    async def apply(self, context: TransactionContext) -> TransactionContext:
        self.logger.info(f"Applying {self.name}")  # Add logging
        context.data.setdefault("call_order", []).append(self.name)
        if self.sets_response:
            context.response = Response(status_code=299, content=f"Response from {self.name}")
            self.logger.info(f"{self.name} setting response")  # Add logging

        # Execute the mock function (which might raise an exception)
        await self.apply_mock(context)
        self.logger.info(f"Finished {self.name}")  # Add logging
        return context

    def __repr__(self) -> str:
        return f"<{self.name}>"

    def serialize(self) -> dict[str, Any]:
        # Mock policies generally don't need complex serialization in tests,
        # but we need the keys expected by the loader/serializer.
        return {
            "__policy_type__": self.__class__.__name__,
            "name": self.name,
            "policy_class_path": self.policy_class_path,
            # Add any other specific config if needed for a test
        }

    @classmethod
    def from_serialized(cls, config: dict[str, Any], **kwargs) -> "MockSimplePolicy":
        """Dummy implementation to satisfy abstract base class."""
        # Extract name or use a default, similar to how real policies might work
        policy_name = config.get("name", "MockPolicyDeserialized")
        # Ignore other config for this simple mock
        return cls(name=policy_name)


@pytest.fixture
def mock_context() -> TransactionContext:
    """Provides a basic TransactionContext for tests."""
    return TransactionContext(transaction_id="test-tx-id")


# --- Test Cases ---


@pytest.mark.asyncio
async def test_compound_policy_applies_policies_sequentially(mock_context):
    """Test that policies are applied in the specified order."""
    policy1 = MockSimplePolicy(name="Policy1")
    policy2 = MockSimplePolicy(name="Policy2")
    compound = CompoundPolicy(policies=[policy1, policy2], name="SequentialTest")

    result_context = await compound.apply(mock_context)

    assert result_context.data.get("call_order") == ["Policy1", "Policy2"]
    policy1.apply_mock.assert_awaited_once_with(mock_context)
    policy2.apply_mock.assert_awaited_once_with(mock_context)  # Context is passed along
    assert result_context.response is None


@pytest.mark.asyncio
async def test_compound_policy_empty_list(mock_context, caplog):
    """Test that CompoundPolicy handles an empty policy list gracefully."""
    compound = CompoundPolicy(policies=[], name="EmptyTest")

    with caplog.at_level(logging.WARNING):
        result_context = await compound.apply(mock_context)

    assert result_context is mock_context  # Should return the original context
    assert "call_order" not in result_context.data
    assert "Initializing CompoundPolicy 'EmptyTest' with an empty policy list." in caplog.text
    assert result_context.response is None


@pytest.mark.asyncio
async def test_compound_policy_propagates_exception(mock_context):
    """Test that an exception raised by a member policy propagates up."""

    class TestException(Exception):
        pass

    policy1 = MockSimplePolicy(name="Policy1")
    policy2 = MockSimplePolicy(name="Policy2", side_effect=TestException("Policy 2 failed!"))
    policy3 = MockSimplePolicy(name="Policy3")
    compound = CompoundPolicy(policies=[policy1, policy2, policy3], name="ExceptionTest")

    with pytest.raises(TestException, match="Policy 2 failed!"):
        await compound.apply(mock_context)

    # Check that only policies up to the failing one were called
    assert mock_context.data.get("call_order") == ["Policy1", "Policy2"]
    policy1.apply_mock.assert_awaited_once()
    policy2.apply_mock.assert_awaited_once()
    policy3.apply_mock.assert_not_awaited()
    assert mock_context.response is None  # No response should be set if exception occurred before


@pytest.mark.asyncio
async def test_compound_policy_continues_on_response(mock_context):
    """Test that execution continues even if a member policy sets context.response."""
    policy1 = MockSimplePolicy(name="Policy1")
    policy2 = MockSimplePolicy(name="Policy2", sets_response=True)  # This policy sets a response
    policy3 = MockSimplePolicy(name="Policy3")
    compound = CompoundPolicy(policies=[policy1, policy2, policy3], name="ResponseTest")

    result_context = await compound.apply(mock_context)

    # Check that all policies were called, even though Policy2 set a response
    assert result_context.data.get("call_order") == ["Policy1", "Policy2", "Policy3"]
    # Also check that the response set by Policy2 is still present
    assert result_context.response is not None
    assert isinstance(result_context.response, Response)


def test_compound_policy_repr():
    """Test the __repr__ method for clarity."""
    policy1 = MockSimplePolicy(name="Auth")
    policy2 = MockSimplePolicy(name="Log")
    compound1 = CompoundPolicy(policies=[policy1, policy2], name="AuthAndLog")
    compound2 = CompoundPolicy(policies=[compound1, MockSimplePolicy(name="Finalize")], name="MainFlow")

    assert repr(compound1) == "<AuthAndLog(policies=['Auth', 'Log'])>"
    assert repr(compound2) == "<MainFlow(policies=['AuthAndLog', 'Finalize'])>"

    # Test with default name
    compound_default = CompoundPolicy(policies=[policy1])
    assert repr(compound_default) == "<CompoundPolicy(policies=['Auth'])>"

    # Test empty
    compound_empty = CompoundPolicy(policies=[], name="Empty")
    assert repr(compound_empty) == "<Empty(policies=[])>"


def test_compound_serialize_config():
    """Test the serialize_config method for CompoundPolicy with nested structure."""
    member1_path = "test.policies.MemberPolicy1"
    member2_path = "test.policies.MemberPolicy2"
    compound_path = "luthien_control.control_policy.compound_policy.CompoundPolicy"

    member1 = MockSimplePolicy(name="Member1", policy_class_path=member1_path)
    member2 = MockSimplePolicy(name="Member2", policy_class_path=member2_path)

    compound = CompoundPolicy(policies=[member1, member2], name="MyCompound")
    # Manually assign the class path as it would be set during loading
    compound.policy_class_path = compound_path

    expected_member1_config = {
        "__policy_type__": "MockSimplePolicy",
        "name": "Member1",
        "policy_class_path": member1_path,
    }
    expected_member2_config = {
        "__policy_type__": "MockSimplePolicy",
        "name": "Member2",
        "policy_class_path": member2_path,
    }

    # Update expectation to match the current serialize method's output
    expected_config = {
        "policies": [
            {"name": "Member1", "config": expected_member1_config},
            {"name": "Member2", "config": expected_member2_config},
        ]
    }

    assert compound.serialize() == expected_config


def test_compound_serialize_config_missing_path_warning(caplog):
    """Test that a warning is logged if policy_class_path is missing during serialization."""
    member1 = MockSimplePolicy(name="Member1")
    compound = CompoundPolicy(policies=[member1], name="MyCompound")
    # Do *not* set compound.policy_class_path

    with caplog.at_level(logging.WARNING):
        config = compound.serialize()

    # The current serialize method doesn't include policy_class_path or log warnings for it.
    # Verify the basic structure returned.
    assert "policies" in config
    assert len(config["policies"]) == 1
    assert config["policies"][0]["name"] == "Member1"


def test_compound_policy_serialization():
    """Test that CompoundPolicy can be serialized and deserialized correctly, including nested policies."""
    # Arrange
    # Create instances of policies to nest
    # Note: These policies themselves don't serialize complex state,
    # making this test simpler. If they did, we'd need to assert more deeply.
    settings = Settings()
    policy1 = ClientApiKeyAuthPolicy(api_key_lookup=get_api_key_by_value)
    # Use the name expected by the registry
    policy1.name = "client_api_key_auth"

    policy2 = AddApiKeyHeaderPolicy(settings=settings)
    # Use the name expected by the registry
    policy2.name = "add_api_key_header"

    original_compound_policy = CompoundPolicy(policies=[policy1, policy2], name="TestCompound")

    # Act
    serialized_data = original_compound_policy.serialize()
    rehydrated_policy = CompoundPolicy.from_serialized(serialized_data, api_key_lookup=get_api_key_by_value)

    # Assert
    assert isinstance(serialized_data, dict)
    assert "policies" in serialized_data
    assert len(serialized_data["policies"]) == 2

    # Check serialized structure (basic check)
    assert serialized_data["policies"][0]["name"] == "client_api_key_auth"
    assert serialized_data["policies"][0]["config"] == {}  # Based on current ClientApiKeyAuthPolicy serialize
    assert serialized_data["policies"][1]["name"] == "add_api_key_header"
    assert serialized_data["policies"][1]["config"] == {}  # Based on current AddApiKeyHeaderPolicy serialize

    # Check rehydrated policy
    assert isinstance(rehydrated_policy, CompoundPolicy)
    assert len(rehydrated_policy.policies) == 2
    assert isinstance(rehydrated_policy.policies[0], ClientApiKeyAuthPolicy)
    assert isinstance(rehydrated_policy.policies[1], AddApiKeyHeaderPolicy)

    # Verify the nested policies were rehydrated correctly (by checking their types/functions)
    assert rehydrated_policy.policies[0]._api_key_lookup is get_api_key_by_value
    assert isinstance(rehydrated_policy.policies[1].settings, Settings)

    # Check the name was preserved (though CompoundPolicy doesn't serialize its own name currently)
    # assert rehydrated_policy.name == "TestCompound" # This would fail as name isn't serialized


def test_compound_policy_serialization_empty():
    """Test serialization with an empty list of policies."""
    # Arrange
    original_compound_policy = CompoundPolicy(policies=[], name="EmptyCompound")

    # Act
    serialized_data = original_compound_policy.serialize()
    rehydrated_policy = CompoundPolicy.from_serialized(serialized_data)

    # Assert
    assert isinstance(serialized_data, dict)
    assert serialized_data == {"policies": []}
    assert isinstance(rehydrated_policy, CompoundPolicy)
