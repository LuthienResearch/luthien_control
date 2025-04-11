import logging
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import Response
from luthien_control.control_policy.compound_policy import CompoundPolicy
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.core.context import TransactionContext

# --- Test Fixtures and Helper Classes ---


class MockSimplePolicy(ControlPolicy):
    """A simple mock policy for testing."""

    def __init__(self, name: str = "MockPolicy", side_effect: Any = None, sets_response: bool = False):
        self.name = name
        self.apply_mock = AsyncMock(side_effect=side_effect)
        self.sets_response = sets_response
        self.logger = logging.getLogger(f"test.policy.{name}")  # Add logger

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

    def serialize_config(self) -> dict[str, Any]:
        # Mock policies generally don't need complex serialization in tests
        return {}


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
async def test_compound_policy_halts_on_response(mock_context):
    """Test that execution halts if a member policy sets context.response."""
    policy1 = MockSimplePolicy(name="Policy1")
    policy2 = MockSimplePolicy(name="Policy2", sets_response=True)  # This policy sets a response
    policy3 = MockSimplePolicy(name="Policy3")
    compound = CompoundPolicy(policies=[policy1, policy2, policy3], name="ResponseTest")

    result_context = await compound.apply(mock_context)

    # Check that only policies up to the one setting the response were called
    assert result_context.data.get("call_order") == ["Policy1", "Policy2"]
    policy1.apply_mock.assert_awaited_once()
    policy2.apply_mock.assert_awaited_once()
    policy3.apply_mock.assert_not_awaited()

    # Check that the response set by policy2 is preserved
    assert result_context.response is not None
    assert isinstance(result_context.response, Response)
    assert result_context.response.status_code == 299
    assert result_context.response.body == b"Response from Policy2"


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
