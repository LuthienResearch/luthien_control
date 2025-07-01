from unittest.mock import Mock, patch

import pytest
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction import Transaction
from sqlalchemy.ext.asyncio import AsyncSession


class MinimalConcretePolicy(ControlPolicy):
    """A minimal concrete implementation for testing purposes."""

    @classmethod
    def get_policy_type_name(cls) -> str:
        """Override to avoid registry lookup for test class."""
        return "MinimalConcretePolicy"

    async def apply(
        self, transaction: Transaction, container: DependencyContainer, session: AsyncSession
    ) -> Transaction:
        # Minimal implementation for testing instantiation
        # Use _ prefix to indicate intentionally unused parameters
        _ = container, session, transaction
        return transaction


def test_cannot_instantiate_abc_directly():
    """Verify that ControlPolicy ABC cannot be instantiated directly."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class ControlPolicy"):
        ControlPolicy()  # type: ignore


def test_subclass_must_implement_abstract_methods():
    """Verify that a subclass missing abstract methods cannot be instantiated."""

    class IncompletePolicy(ControlPolicy):
        # Missing apply method
        pass

    with pytest.raises(TypeError, match="Can't instantiate abstract class IncompletePolicy"):
        IncompletePolicy()  # type: ignore


def test_can_instantiate_concrete_subclass():
    """Verify that a correctly implemented concrete subclass can be instantiated."""
    try:
        policy = MinimalConcretePolicy()
        assert isinstance(policy, ControlPolicy)
    except TypeError:
        pytest.fail("MinimalConcretePolicy should be instantiable but raised TypeError.")


def test_from_serialized_invalid_type():
    """Test ControlPolicy.from_serialized with missing or invalid type."""
    # Test with missing type
    with pytest.raises(ValueError) as exc_info:
        ControlPolicy.from_serialized({})
    assert "must include a 'type' field" in str(exc_info.value)

    # Test with non-string type
    with pytest.raises(ValueError) as exc_info:
        ControlPolicy.from_serialized({"type": 123})
    assert "must include a 'type' field as a string" in str(exc_info.value)


def test_from_serialized_unknown_type():
    """Test ControlPolicy.from_serialized with unknown policy type."""
    with pytest.raises(ValueError) as exc_info:
        ControlPolicy.from_serialized({"type": "unknown_policy_type"})
    assert "Unknown policy type" in str(exc_info.value)


@patch("luthien_control.control_policy.registry.POLICY_NAME_TO_CLASS")
def test_from_serialized_valid(mock_registry):
    """Test ControlPolicy.from_serialized with valid type."""
    # Create a mock policy class
    mock_policy_class = Mock()
    mock_policy = Mock()
    mock_policy_class.model_validate.return_value = mock_policy

    # Set up the registry to return our mock class
    mock_registry.get.return_value = mock_policy_class

    # Test serialized data
    serialized = {"type": "mock_policy", "name": "test_policy"}

    # Call the method
    result = ControlPolicy.from_serialized(serialized)  # type: ignore

    # Verify the result
    assert result == mock_policy
    mock_registry.get.assert_called_once_with("mock_policy")
    mock_policy_class.model_validate.assert_called_once()
