# pyright: reportCallIssue=false, reportAttributeAccessIssue=false, reportUnhashable=false
from typing import Literal
from unittest.mock import Mock, patch

import pytest
from luthien_control.control_policy.conditions import EqualsCondition, path
from luthien_control.control_policy.conditions.condition import Condition
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.transaction import Transaction
from pydantic import Field


class MockCondition(Condition):
    """A concrete implementation of Condition for testing abstract methods."""

    type: Literal["mock"] = Field(default="mock")
    value: bool = Field(default=True)

    def evaluate(self, transaction: Transaction) -> bool:
        return self.value


class TestConditionBaseClass:
    """Tests for the Condition base class methods."""

    def test_from_serialized_invalid_type_missing(self):
        """Test Condition.from_serialized with missing type."""
        with pytest.raises(ValueError, match="must include a 'type' field"):
            Condition.from_serialized({})

    def test_from_serialized_invalid_type_none(self):
        """Test Condition.from_serialized with None type."""
        with pytest.raises(ValueError, match="must include a 'type' field as a string"):
            Condition.from_serialized({"type": None})

    def test_from_serialized_invalid_type_non_string(self):
        """Test Condition.from_serialized with non-string type."""
        with pytest.raises(ValueError, match="must include a 'type' field as a string"):
            Condition.from_serialized({"type": 123})

    def test_from_serialized_unknown_type(self):
        """Test Condition.from_serialized with unknown condition type."""
        with pytest.raises(ValueError, match="Unknown condition type"):
            Condition.from_serialized({"type": "unknown_condition_type"})

    @patch("luthien_control.control_policy.conditions.condition.safe_model_validate")
    @patch("luthien_control.control_policy.conditions.registry.NAME_TO_CONDITION_CLASS")
    def test_from_serialized_valid(self, mock_registry, mock_safe_model_validate):
        """Test Condition.from_serialized with valid type."""
        # Create a mock condition class and instance
        mock_condition_class = Mock()
        mock_condition = Mock()
        mock_safe_model_validate.return_value = mock_condition

        # Set up the registry to return our mock class
        mock_registry.get.return_value = mock_condition_class

        # Test serialized data
        serialized: SerializableDict = {"type": "mock_condition", "key": "test", "value": "value"}

        # Call the method
        result = Condition.from_serialized(serialized)

        # Verify the result
        assert result == mock_condition
        mock_registry.get.assert_called_once_with("mock_condition")
        mock_safe_model_validate.assert_called_once_with(mock_condition_class, serialized)

    def test_from_serialized_no_class_found(self):
        """Test Condition.from_serialized when no class is found in registry."""
        with pytest.raises(ValueError, match="Unknown condition type 'nonexistent'"):
            Condition.from_serialized({"type": "nonexistent"})

    def test_repr_format(self):
        """Test the __repr__ format."""
        condition = EqualsCondition(path("test"), "value")
        repr_str = repr(condition)
        assert "EqualsCondition" in repr_str
        assert "test" in repr_str
        assert "value" in repr_str

    def test_hash_consistency(self):
        """Test that hash is consistent and based on string representation."""
        condition = EqualsCondition(path("test"), "value")
        expected_hash = hash(str(condition))
        assert hash(condition) == expected_hash

    def test_eq_different_class(self):
        """Test __eq__ with different class types."""
        condition1 = EqualsCondition(path("test"), "value")
        condition2 = "not a condition"
        assert condition1 != condition2

    def test_eq_same_class_different_serialization(self):
        """Test __eq__ with same class but different serialization."""
        condition1 = EqualsCondition(path("test"), "value1")
        condition2 = EqualsCondition(path("test"), "value2")
        assert condition1 != condition2

    def test_eq_same_class_same_serialization(self):
        """Test __eq__ with same class and same serialization."""
        condition1 = EqualsCondition(path("test"), "value")
        condition2 = EqualsCondition(path("test"), "value")
        assert condition1 == condition2

    def test_repr_base_implementation(self):
        """Test the base __repr__ implementation."""
        mock_condition = MockCondition(value=True)
        repr_str = repr(mock_condition)
        assert "MockCondition" in repr_str
        assert "mock" in repr_str
        assert "True" in repr_str
