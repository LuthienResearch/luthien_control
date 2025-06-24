from unittest.mock import MagicMock, Mock, patch

import pytest
from luthien_control.core.transaction import Transaction
from luthien_control.new_control_policy.conditions.comparisons import EqualsCondition
from luthien_control.new_control_policy.conditions.condition import Condition
from luthien_control.new_control_policy.serialization import SerializableDict


class MockCondition(Condition):
    """A concrete implementation of Condition for testing abstract methods."""

    type = "mock"

    def __init__(self, value: bool = True):
        self.value = value

    def evaluate(self, transaction: Transaction) -> bool:
        return self.value

    def serialize(self) -> SerializableDict:
        return {"type": self.type, "value": self.value}


class TestConditionBaseClass:
    """Tests for the Condition base class methods."""

    def test_evaluate_abstract_method(self):
        """Test that the evaluate method is abstract."""
        mock_transaction = MagicMock(spec=Transaction)
        # Call the abstract method directly to get coverage
        result = Condition.evaluate(None, mock_transaction)  # type: ignore
        assert result is None

    def test_serialize_abstract_method(self):
        """Test that the serialize method is abstract."""
        # Call the abstract method directly to get coverage
        result = Condition.serialize(None)  # type: ignore
        assert result is None

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

    @patch("luthien_control.new_control_policy.conditions.registry.NAME_TO_CONDITION_CLASS")
    def test_from_serialized_valid(self, mock_registry):
        """Test Condition.from_serialized with valid type."""
        # Create a mock condition class
        mock_condition_class = Mock()
        mock_condition = Mock()
        mock_condition_class.from_serialized.return_value = mock_condition

        # Set up the registry to return our mock class
        mock_registry.get.return_value = mock_condition_class

        # Test serialized data
        serialized: SerializableDict = {"type": "mock_condition", "key": "test", "value": "value"}

        # Call the method
        result = Condition.from_serialized(serialized)

        # Verify the result
        assert result == mock_condition
        mock_registry.get.assert_called_once_with("mock_condition")
        mock_condition_class.from_serialized.assert_called_once_with(serialized)

    def test_from_serialized_no_class_found(self):
        """Test Condition.from_serialized when no class is found in registry."""
        with pytest.raises(ValueError, match="Unknown condition type 'nonexistent'"):
            Condition.from_serialized({"type": "nonexistent"})

    def test_repr_format(self):
        """Test the __repr__ format."""
        condition = EqualsCondition(key="test", value="value")
        repr_str = repr(condition)
        assert "EqualsCondition" in repr_str
        assert "test" in repr_str
        assert "value" in repr_str

    def test_hash_consistency(self):
        """Test that hash is consistent and based on string representation."""
        condition = EqualsCondition(key="test", value="value")
        expected_hash = hash(str(condition))
        assert hash(condition) == expected_hash

    def test_eq_different_class(self):
        """Test __eq__ with different class types."""
        condition1 = EqualsCondition(key="test", value="value")
        condition2 = "not a condition"
        assert condition1 != condition2

    def test_eq_same_class_different_serialization(self):
        """Test __eq__ with same class but different serialization."""
        condition1 = EqualsCondition(key="test", value="value1")
        condition2 = EqualsCondition(key="test", value="value2")
        assert condition1 != condition2

    def test_eq_same_class_same_serialization(self):
        """Test __eq__ with same class and same serialization."""
        condition1 = EqualsCondition(key="test", value="value")
        condition2 = EqualsCondition(key="test", value="value")
        assert condition1 == condition2

    def test_repr_base_implementation(self):
        """Test the base __repr__ implementation."""
        mock_condition = MockCondition(True)
        repr_str = repr(mock_condition)
        assert "MockCondition" in repr_str
        assert "mock" in repr_str
        assert "True" in repr_str
