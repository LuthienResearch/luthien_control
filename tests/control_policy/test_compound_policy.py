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
from sqlalchemy.ext.asyncio import AsyncSession
from luthien_control.dependency_container import DependencyContainer

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

    async def apply(
        self,
        context: TransactionContext,
        container: DependencyContainer,
        session: AsyncSession,
    ) -> TransactionContext:
        self.logger.info(f"Applying {self.name}")
        call_order = context.data.setdefault("call_order", [])
        call_order.append(self.name)

        if self.sets_response:
            context.response = Response(status_code=299, content=f"Response from {self.name}")
            self.logger.info(f"{self.name} setting response")

        await self.apply_mock(context, container=container, session=session)
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
def base_transaction_context() -> TransactionContext:
    """Provides a basic TransactionContext for tests."""
    return TransactionContext(transaction_id="test-tx-id")


# --- Test Cases ---


@pytest.mark.asyncio
async def test_compound_policy_applies_policies_sequentially(
    base_transaction_context,
    mock_db_session: AsyncSession,
    mock_container: DependencyContainer,
):
    """Test that policies are applied in the specified order."""
    policy1 = MockSimplePolicy(name="Policy1")
    policy2 = MockSimplePolicy(name="Policy2")
    compound = CompoundPolicy(policies=[policy1, policy2], name="SequentialTest")

    # Keep track of context references
    context_before_policy1 = base_transaction_context

    # Pass mock session and container
    result_context = await compound.apply(
        base_transaction_context,
        container=mock_container,
        session=mock_db_session,
    )

    # Assertions
    assert result_context.data.get("call_order") == ["Policy1", "Policy2"]
    # Ensure the mock policies were called with the correct context
    assert policy1.apply_mock.call_args[0][0] == context_before_policy1
    # The context passed to policy2 should be the result of policy1
    assert (
        policy2.apply_mock.call_args[0][0] == context_before_policy1
    )  # Assuming MockSimplePolicy returns same context
    # Check session and container were passed
    policy1.apply_mock.assert_awaited_once_with(
        base_transaction_context, container=mock_container, session=mock_db_session
    )
    policy2.apply_mock.assert_awaited_once_with(
        base_transaction_context, container=mock_container, session=mock_db_session
    )
    assert result_context is base_transaction_context  # Verify same context object is returned if not modified


@pytest.mark.asyncio
async def test_compound_policy_empty_list(
    base_transaction_context,
    caplog,
    mock_db_session: AsyncSession,
    mock_container: DependencyContainer,
):
    """Test that CompoundPolicy handles an empty policy list gracefully."""
    compound = CompoundPolicy(policies=[], name="EmptyTest")

    with caplog.at_level(logging.WARNING):
        result_context = await compound.apply(
            base_transaction_context,
            container=mock_container,
            session=mock_db_session,
        )

    assert result_context is base_transaction_context
    assert "Initializing CompoundPolicy 'EmptyTest' with an empty policy list." in caplog.text


@pytest.mark.asyncio
async def test_compound_policy_propagates_exception(
    base_transaction_context,
    mock_db_session: AsyncSession,
    mock_container: DependencyContainer,
):
    """Test that an exception raised by a member policy propagates up."""

    class TestException(Exception):
        pass

    policy1 = MockSimplePolicy(name="Policy1")
    policy2 = MockSimplePolicy(side_effect=TestException("Policy 2 failed!"), name="Policy2")
    policy3 = MockSimplePolicy(name="Policy3")
    compound = CompoundPolicy(policies=[policy1, policy2, policy3], name="ExceptionTest")

    with pytest.raises(TestException, match="Policy 2 failed!"):
        await compound.apply(
            base_transaction_context,
            container=mock_container,
            session=mock_db_session,
        )

    # Check that policy1 was called, but policy3 was not
    assert base_transaction_context.data.get("call_order") == ["Policy1", "Policy2"]
    policy1.apply_mock.assert_awaited_once()
    policy2.apply_mock.assert_awaited_once()
    policy3.apply_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_compound_policy_continues_on_response(
    base_transaction_context,
    mock_db_session: AsyncSession,
    mock_container: DependencyContainer,
):
    """Test that execution continues even if a member policy sets context.response."""
    policy1 = MockSimplePolicy(name="Policy1")
    policy2 = MockSimplePolicy(sets_response=True, name="Policy2")  # This policy sets a response
    policy3 = MockSimplePolicy(name="Policy3")
    compound = CompoundPolicy(policies=[policy1, policy2, policy3], name="ResponseTest")

    # Track the context object
    context_before_apply = base_transaction_context

    # Pass mock session and container
    result_context = await compound.apply(
        base_transaction_context,
        container=mock_container,
        session=mock_db_session,
    )

    # Ensure all policies were still called
    policy1.apply_mock.assert_awaited_once()
    policy2.apply_mock.assert_awaited_once()
    policy3.apply_mock.assert_awaited_once()

    # The final result should be the original context object
    assert result_context is context_before_apply
    # Check that policy 2 did set the response on the context
    assert result_context.response is not None
    assert result_context.response.body == b"Response from Policy2"


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
    policy1 = ClientApiKeyAuthPolicy()
    policy2 = AddApiKeyHeaderPolicy(name="AddOpenAIKey")

    # Manually set policy_type for serialization registry lookup (usually handled by DB loading)
    # Ensure registry maps these types correctly

    original_compound_policy = CompoundPolicy(policies=[policy1, policy2], name="TestCompound")

    # Act
    serialized_data = original_compound_policy.serialize()
    rehydrated_policy = await CompoundPolicy.from_serialized(serialized_data)

    # Assert
    assert isinstance(serialized_data, dict)
    assert "policies" in serialized_data
    assert len(serialized_data["policies"]) == 2

    assert serialized_data["policies"][0]["type"] == "ClientApiKeyAuth"
    assert serialized_data["policies"][0]["config"] == {}
    assert serialized_data["policies"][1]["type"] == "AddApiKeyHeader"
    assert serialized_data["policies"][1]["config"] == {
        "name": "AddOpenAIKey",
    }

    assert isinstance(rehydrated_policy, CompoundPolicy)
    assert len(rehydrated_policy.policies) == 2
    assert isinstance(rehydrated_policy.policies[0], ClientApiKeyAuthPolicy)
    assert isinstance(rehydrated_policy.policies[1], AddApiKeyHeaderPolicy)
    # Check the name is correct after rehydration
    assert rehydrated_policy.policies[1].name == "AddOpenAIKey"


@pytest.mark.asyncio
async def test_compound_policy_serialization_empty():
    """Test serialization with an empty list of policies."""
    # Arrange
    original_compound_policy = CompoundPolicy(policies=[], name="EmptyCompound")

    # Act
    serialized_data = original_compound_policy.serialize()
    rehydrated_policy = await CompoundPolicy.from_serialized(serialized_data)

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
