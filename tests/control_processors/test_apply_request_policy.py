"""Tests for the ApplyRequestPolicyProcessor."""

from unittest.mock import MagicMock, patch

import pytest
from luthien_control.control_processors.apply_request_policy import ApplyRequestPolicyProcessor
from luthien_control.core.context import TransactionContext

# Keep using the mock exception for isolation
from luthien_control.testing.mocks.exceptions import MockPolicyViolationError


# Mock Policies (can remain defined here or moved to a common testing mock location)
class MockSuccessPolicy:
    async def apply_request(self, context: TransactionContext) -> TransactionContext:
        context.data["mock_success_policy_applied"] = True
        return context


class MockFailurePolicy:
    async def apply_request(self, context: TransactionContext) -> TransactionContext:
        raise MockPolicyViolationError("Mock failure policy triggered!")


@pytest.fixture
def mock_policy_loader() -> MagicMock:
    """Provides a mock PolicyLoader instance."""
    loader = MagicMock()
    # Configure default return value (can be overridden in tests)
    loader.get_request_policies.return_value = []
    return loader


# Patch the actual PolicyViolationError imported by the processor module
@patch("luthien_control.control_processors.apply_request_policy.PolicyViolationError", MockPolicyViolationError)
@pytest.mark.asyncio
async def test_apply_request_policy_success(mock_policy_loader: MagicMock):
    """Test successful application using a mocked loader."""
    # Configure mock loader to return the success policy
    mock_policy_loader.get_request_policies.return_value = [MockSuccessPolicy()]

    processor = ApplyRequestPolicyProcessor(policy_loader=mock_policy_loader)
    context = TransactionContext(transaction_id="test-success-123")

    result_context = await processor.process(context)

    assert result_context is context
    # Verify the loader was asked for request policies
    mock_policy_loader.get_request_policies.assert_called_once()
    # Assert that the mock policy modified the context
    assert context.data.get("mock_success_policy_applied") is True


# Patch the actual PolicyViolationError imported by the processor module
@patch("luthien_control.control_processors.apply_request_policy.PolicyViolationError", MockPolicyViolationError)
@pytest.mark.asyncio
async def test_apply_request_policy_violation(mock_policy_loader: MagicMock):
    """Test policy violation using a mocked loader."""
    # Configure mock loader to return the failure policy
    mock_policy_loader.get_request_policies.return_value = [MockFailurePolicy()]

    processor = ApplyRequestPolicyProcessor(policy_loader=mock_policy_loader)
    context = TransactionContext(transaction_id="test-violation-456")

    # Expect MockPolicyViolationError to be raised by the loaded policy
    with pytest.raises(MockPolicyViolationError, match="Mock failure policy triggered!"):
        await processor.process(context)

    # Verify the loader was asked for request policies
    mock_policy_loader.get_request_policies.assert_called_once()


@pytest.mark.asyncio
async def test_apply_request_policy_no_policies(mock_policy_loader: MagicMock):
    """Test behavior when the loader returns no request policies."""
    # Loader already configured in fixture to return [] by default
    processor = ApplyRequestPolicyProcessor(policy_loader=mock_policy_loader)
    context = TransactionContext(transaction_id="test-no-policies-789")

    # Should execute without error and return context unmodified
    result_context = await processor.process(context)

    assert result_context is context
    mock_policy_loader.get_request_policies.assert_called_once()
    # Check data hasn't been modified by mock policies
    assert "mock_success_policy_applied" not in context.data
