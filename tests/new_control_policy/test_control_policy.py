from typing import Any, cast
from unittest.mock import Mock, patch

import pytest
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction import Transaction
from luthien_control.new_control_policy.control_policy import ControlPolicy
from luthien_control.new_control_policy.serialization import SerializableDict
from sqlalchemy.ext.asyncio import AsyncSession


class MinimalConcretePolicy(ControlPolicy):
    """A minimal concrete implementation for testing purposes."""

    name = "minimal_concrete"

    async def apply(
        self, transaction: Transaction, container: DependencyContainer, session: AsyncSession
    ) -> Transaction:
        # Minimal implementation for testing instantiation
        # Use _ prefix to indicate intentionally unused parameters
        _ = container, session, transaction
        return transaction

    def get_policy_config(self) -> SerializableDict:
        # Minimal implementation for testing instantiation
        return {"name": self.name}

    @classmethod
    def from_serialized(cls, config: SerializableDict, **kwargs: Any) -> "MinimalConcretePolicy":
        # Minimal implementation for testing instantiation
        _ = kwargs  # Mark as intentionally unused
        instance = cls()
        name_val = config.get("name", cls.name)
        if not isinstance(name_val, str):
            # Fallback or raise error if name is not a string, as per your project's error handling
            # For this example, let's assume it should default or raise if type is wrong.
            # This specific handling might need adjustment based on stricter type requirements.
            if name_val is not None:
                # Attempt to cast or handle non-str cases appropriately if they are valid
                # For now, let's assume if it's not None, it *should* have been a string.
                # A more robust solution might involve raising a TypeError or using a default.
                pass  # Or raise TypeError(f"Expected name to be a string, got {type(name_val)}")
        instance.name = cast(str, name_val) if name_val is not None else cls.name
        return instance


def test_cannot_instantiate_abc_directly():
    """Verify that ControlPolicy ABC cannot be instantiated directly."""
    with pytest.raises(TypeError, match="Can't instantiate abstract class ControlPolicy"):
        ControlPolicy()  # type: ignore


def test_subclass_must_implement_abstract_methods():
    """Verify that a subclass missing abstract methods cannot be instantiated."""

    class IncompletePolicy(ControlPolicy):
        name = "incomplete"

        # Missing apply, serialize, from_serialized

    with pytest.raises(TypeError, match="Can't instantiate abstract class IncompletePolicy"):
        IncompletePolicy()  # type: ignore


def test_can_instantiate_concrete_subclass():
    """Verify that a correctly implemented concrete subclass can be instantiated."""
    try:
        policy = MinimalConcretePolicy()
        assert isinstance(policy, ControlPolicy)
        assert policy.name == "minimal_concrete"
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


@patch("luthien_control.new_control_policy.registry.POLICY_NAME_TO_CLASS")
def test_from_serialized_valid(mock_registry):
    """Test ControlPolicy.from_serialized with valid type."""
    # Create a mock policy class
    mock_policy_class = Mock()
    mock_policy = Mock()
    mock_policy_class.from_serialized.return_value = mock_policy

    # Set up the registry to return our mock class
    mock_registry.get.return_value = mock_policy_class

    # Test serialized data
    serialized = {"type": "mock_policy", "name": "test_policy"}

    # Call the method
    result = ControlPolicy.from_serialized(serialized)  # type: ignore

    # Verify the result
    assert result == mock_policy
    mock_registry.get.assert_called_once_with("mock_policy")
    mock_policy_class.from_serialized.assert_called_once_with(serialized)


