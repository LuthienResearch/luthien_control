import logging
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Response
from luthien_control.config.settings import Settings
from luthien_control.control_policy.add_api_key_header import AddApiKeyHeaderPolicy
from luthien_control.control_policy.client_api_key_auth import ClientApiKeyAuthPolicy
from luthien_control.control_policy.compound_policy import CompoundPolicy
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.exceptions import PolicyLoadError
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.transaction_context import TransactionContext
from luthien_control.db.client_api_key_crud import get_api_key_by_value

# --- Test Fixtures and Helper Classes ---


class MockSimplePolicy(ControlPolicy):
    """A simple mock policy for testing."""

    def __init__(
        self,
        side_effect: Any = None,
        sets_response: bool = False,
        name: Optional[str] = None,
    ):
        self.apply_mock = AsyncMock(side_effect=side_effect)
        self.sets_response = sets_response
        self.logger = logging.getLogger(self.__class__.__name__)
        self.name = name or self.__class__.__name__

    async def apply(self, context: TransactionContext) -> TransactionContext:
        self.logger.info(f"Applying {self.name}")
        call_order = context.data.setdefault("call_order", [])
        call_order.append(self.name)

        if self.sets_response:
            context.response = Response(status_code=299, content=f"Response from {self.name}")
            self.logger.info(f"{self.name} setting response")

        await self.apply_mock(context)
        self.logger.info(f"Finished {self.name}")
        return context

    def __repr__(self) -> str:
        return f"<{self.name}>"

    def serialize(self) -> SerializableDict:
        return {}

    @classmethod
    def from_serialized(cls, config: SerializableDict, **kwargs) -> "MockSimplePolicy":
        """Dummy implementation to satisfy abstract base class."""
        return cls()


@pytest.fixture
def mock_context() -> TransactionContext:
    """Provides a basic TransactionContext for tests."""
    return TransactionContext(transaction_id="test-tx-id")


# --- Test Cases ---


@pytest.mark.asyncio
async def test_compound_policy_applies_policies_sequentially(mock_context):
    """Test that policies are applied in the specified order."""
    policy1 = MockSimplePolicy()
    policy2 = MockSimplePolicy()
    compound = CompoundPolicy(policies=[policy1, policy2], name="SequentialTest")

    result_context = await compound.apply(mock_context)

    assert result_context.data.get("call_order") == ["MockSimplePolicy", "MockSimplePolicy"]
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

    policy1 = MockSimplePolicy()
    policy2 = MockSimplePolicy(side_effect=TestException("Policy 2 failed!"))
    policy3 = MockSimplePolicy()
    compound = CompoundPolicy(policies=[policy1, policy2, policy3], name="ExceptionTest")

    with pytest.raises(TestException, match="Policy 2 failed!"):
        await compound.apply(mock_context)

    assert mock_context.data.get("call_order") == ["MockSimplePolicy", "MockSimplePolicy"]
    policy1.apply_mock.assert_awaited_once()
    policy2.apply_mock.assert_awaited_once()
    policy3.apply_mock.assert_not_awaited()
    assert mock_context.response is None  # No response should be set if exception occurred before


@pytest.mark.asyncio
async def test_compound_policy_continues_on_response(mock_context):
    """Test that execution continues even if a member policy sets context.response."""
    policy1 = MockSimplePolicy()
    policy2 = MockSimplePolicy(sets_response=True)  # This policy sets a response
    policy3 = MockSimplePolicy()
    compound = CompoundPolicy(policies=[policy1, policy2, policy3], name="ResponseTest")

    result_context = await compound.apply(mock_context)

    assert result_context.data.get("call_order") == ["MockSimplePolicy", "MockSimplePolicy", "MockSimplePolicy"]
    assert result_context.response is not None
    assert isinstance(result_context.response, Response)


def test_compound_policy_repr():
    """Test the __repr__ method for clarity."""
    policy1 = MockSimplePolicy(name="Policy1")
    policy2 = MockSimplePolicy(name="Policy2")
    compound1 = CompoundPolicy(policies=[policy1, policy2], name="AuthAndLog")
    compound2 = CompoundPolicy(policies=[compound1, MockSimplePolicy(name="Policy3")], name="MainFlow")

    assert repr(compound1) == "<AuthAndLog(policies=[Policy1 <MockSimplePolicy>, Policy2 <MockSimplePolicy>])>"
    assert repr(compound2) == "<MainFlow(policies=[AuthAndLog <CompoundPolicy>, Policy3 <MockSimplePolicy>])>"

    compound_default = CompoundPolicy(policies=[policy1])
    assert repr(compound_default) == "<CompoundPolicy(policies=[Policy1 <MockSimplePolicy>])>"

    compound_empty = CompoundPolicy(policies=[], name="Empty")
    assert repr(compound_empty) == "<Empty(policies=[])>"


def test_compound_serialize_config():
    """Test the serialize_config method for CompoundPolicy with nested structure."""

    member1 = MockSimplePolicy(name="MockSimplePolicy1")
    member2 = MockSimplePolicy(name="MockSimplePolicy2")

    compound = CompoundPolicy(policies=[member1, member2], name="MyCompound")

    expected_member1_config = member1.serialize()
    expected_member2_config = member2.serialize()

    expected_config = {
        "policies": [
            {"type": None, "config": expected_member1_config},
            {"type": None, "config": expected_member2_config},
        ]
    }

    assert compound.serialize() == expected_config


@pytest.mark.asyncio
async def test_compound_policy_serialization():
    """Test that CompoundPolicy can be serialized and deserialized correctly, including nested policies."""
    # Arrange
    settings = Settings()
    policy1 = ClientApiKeyAuthPolicy()
    policy1.policy_type = "ClientApiKeyAuth"

    policy2 = AddApiKeyHeaderPolicy(settings=settings)
    policy2.policy_type = "AddApiKeyHeader"

    original_compound_policy = CompoundPolicy(policies=[policy1, policy2], name="TestCompound")

    # Act
    serialized_data = original_compound_policy.serialize()
    rehydrated_policy = await CompoundPolicy.from_serialized(
        serialized_data,
        settings=settings,
    )

    # Assert
    assert isinstance(serialized_data, dict)
    assert "policies" in serialized_data
    assert len(serialized_data["policies"]) == 2

    assert serialized_data["policies"][0]["type"] == "ClientApiKeyAuth"
    assert serialized_data["policies"][0]["config"] == {"name": policy1.name}
    assert serialized_data["policies"][1]["type"] == "AddApiKeyHeader"
    assert serialized_data["policies"][1]["config"] == {"name": policy2.name}

    assert isinstance(rehydrated_policy, CompoundPolicy)
    assert len(rehydrated_policy.policies) == 2
    assert isinstance(rehydrated_policy.policies[0], ClientApiKeyAuthPolicy)
    assert isinstance(rehydrated_policy.policies[1], AddApiKeyHeaderPolicy)
    assert rehydrated_policy.policies[1].settings is settings


@pytest.mark.asyncio
async def test_compound_policy_serialization_empty():
    """Test serialization with an empty list of policies."""
    # Arrange
    original_compound_policy = CompoundPolicy(policies=[], name="EmptyCompound")

    # Act
    serialized_data = original_compound_policy.serialize()
    rehydrated_policy = await CompoundPolicy.from_serialized(serialized_data, settings=Settings())

    # Assert
    assert isinstance(serialized_data, dict)
    assert serialized_data == {"policies": []}
    assert isinstance(rehydrated_policy, CompoundPolicy)
    assert len(rehydrated_policy.policies) == 0


@pytest.mark.asyncio
async def test_compound_policy_serialization_missing_policies_key():
    """Test deserialization failure when 'policies' key is missing."""
    # Arrange
    invalid_config = {"some_other_key": "value"}

    # Act & Assert
    with pytest.raises(PolicyLoadError, match="CompoundPolicy config missing 'policies' list"):
        await CompoundPolicy.from_serialized(invalid_config)


@pytest.mark.asyncio
async def test_compound_policy_serialization_invalid_policy_item():
    """Test deserialization failure with invalid item in 'policies' list."""
    invalid_config = {
        "policies": [
            {"type": "ClientApiKeyAuth", "config": {}},
            "not a dict",  # Invalid item
        ]
    }
    with pytest.raises(PolicyLoadError, match="Item at index 1 in CompoundPolicy 'policies' is not a dictionary"):
        await CompoundPolicy.from_serialized(invalid_config)


@patch("luthien_control.control_policy.compound_policy.load_policy", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_compound_policy_serialization_load_error(mock_load_policy):
    """Test error propagation when loading a member policy fails."""
    config = {
        "policies": [
            {"type": "policy1", "config": {}},
            {"type": "policy_that_fails", "config": {}},
        ]
    }
    mock_load_policy.side_effect = [MagicMock(spec=ControlPolicy), PolicyLoadError("Mocked load failure")]

    with pytest.raises(PolicyLoadError, match="Failed to load member policy.*within CompoundPolicy"):
        await CompoundPolicy.from_serialized(config)


@patch("luthien_control.control_policy.compound_policy.load_policy", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_compound_policy_serialization_unexpected_error(mock_load_policy):
    """Test handling of unexpected errors during member policy loading."""
    config = {
        "policies": [
            {"type": "policy1", "config": {}},
        ]
    }
    mock_load_policy.side_effect = ValueError("Unexpected internal error")

    with pytest.raises(PolicyLoadError, match="Unexpected error loading member policy.*"):
        await CompoundPolicy.from_serialized(config)
