from typing import Any, Optional, cast
from unittest.mock import mock_open, patch

import pytest
from luthien_control.new_control_policy.exceptions import PolicyLoadError
from luthien_control.new_control_policy.loader import load_policy, load_policy_from_file
from luthien_control.new_control_policy.serialization import SerializableDict, SerializedPolicy

# --- Test Fixtures and Mocks ---


# Mock ControlPolicy class for testing
class MockPolicy:
    name = "mock_policy"

    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        # Allow setting name via config for testing name assignment
        self.name = self.config.get("name", self.name)

    @classmethod
    def from_serialized(cls, config: SerializableDict, **kwargs: Any) -> "MockPolicy":
        if config.get("fail_load", False):
            raise ValueError("Simulated instantiation failure")
        return cls(config=cast(dict, config))

    def serialize(self) -> SerializableDict:
        return self.config


# Mock registry
MOCK_REGISTRY = {"mock_policy": MockPolicy}

# --- Test Cases ---


@pytest.mark.parametrize(
    "config,expected_name",
    [
        ({"key": "value", "name": "instance_one"}, "instance_one"),  # Name from config
        ({"key": "value"}, "mock_policy"),  # Default name from class
    ],
)
@patch("luthien_control.new_control_policy.registry.POLICY_NAME_TO_CLASS", MOCK_REGISTRY)
def test_load_policy_success(config, expected_name):
    """Test successful loading of a known policy type with and without name in config."""
    serialized_policy_obj = SerializedPolicy(type="mock_policy", config=config)
    policy = load_policy(serialized_policy_obj)

    assert isinstance(policy, MockPolicy)
    assert policy.config == config
    assert policy.name == expected_name


@patch("luthien_control.new_control_policy.registry.POLICY_NAME_TO_CLASS", MOCK_REGISTRY)
def test_load_policy_unknown_type():
    """Test loading fails for an unknown policy type."""
    serialized_policy_obj = SerializedPolicy(type="unknown_policy", config={})

    with pytest.raises(PolicyLoadError, match="Unknown policy type: 'unknown_policy'"):
        load_policy(serialized_policy_obj)


@patch("luthien_control.new_control_policy.registry.POLICY_NAME_TO_CLASS", MOCK_REGISTRY)
def test_load_policy_instantiation_error():
    """Test loading fails when the policy's from_serialized raises an error."""
    serialized_policy_obj = SerializedPolicy(
        type="mock_policy",
        config={"fail_load": True},  # Instruct mock to fail
    )

    with pytest.raises(PolicyLoadError, match="Error instantiating policy 'mock_policy'"):
        load_policy(serialized_policy_obj)


@pytest.mark.parametrize(
    "policy_type,policy_config,expected_error",
    [
        (123, {}, "Policy 'type' must be a string"),
        ("mock_policy", "not_a_dict", "Policy 'config' must be a dictionary"),
    ],
)
@patch("luthien_control.new_control_policy.registry.POLICY_NAME_TO_CLASS", MOCK_REGISTRY)
def test_load_policy_input_validation(policy_type, policy_config, expected_error):
    """Test loading fails with invalid input formats."""
    serialized_policy_obj = SerializedPolicy(type=policy_type, config=policy_config)

    with pytest.raises(PolicyLoadError, match=expected_error):
        load_policy(serialized_policy_obj)


# --- Tests for load_policy_from_file ---


@patch("luthien_control.new_control_policy.registry.POLICY_NAME_TO_CLASS", MOCK_REGISTRY)
@patch("builtins.open", new_callable=mock_open, read_data='{"type": "mock_policy", "config": {"key": "value"}}')
def test_load_policy_from_file_success(mock_file):
    """Test successful loading of a policy from a file."""
    policy = load_policy_from_file("test_policy.json")

    assert isinstance(policy, MockPolicy)
    assert policy.config == {"key": "value"}
    mock_file.assert_called_once_with("test_policy.json", "r")


@pytest.mark.parametrize(
    "file_content,expected_error",
    [
        ('"not_a_dict"', "Policy data loaded from test_policy.json must be a dictionary"),
        ('{"config": {"key": "value"}}', "Policy file test_policy.json must contain a 'type' field as a string"),
        (
            '{"type": 123, "config": {"key": "value"}}',
            "Policy file test_policy.json must contain a 'type' field as a string",
        ),
        ('{"type": "mock_policy"}', "Policy file test_policy.json must contain a 'config' field as a dictionary"),
        (
            '{"type": "mock_policy", "config": "not_a_dict"}',
            "Policy file test_policy.json must contain a 'config' field as a dictionary",
        ),
    ],
)
@patch("luthien_control.new_control_policy.registry.POLICY_NAME_TO_CLASS", MOCK_REGISTRY)
def test_load_policy_from_file_validation_errors(file_content, expected_error):
    """Test loading fails with various file validation scenarios."""
    with patch("builtins.open", new_callable=mock_open, read_data=file_content):
        with pytest.raises(PolicyLoadError, match=expected_error):
            load_policy_from_file("test_policy.json")


@patch("luthien_control.new_control_policy.registry.POLICY_NAME_TO_CLASS", MOCK_REGISTRY)
@patch("builtins.open", new_callable=mock_open, read_data="{invalid json}")
def test_load_policy_from_file_invalid_json(mock_file):
    """Test loading fails when file contains invalid JSON."""
    import json

    # The json.JSONDecodeError will be raised during json.load()
    with pytest.raises(json.JSONDecodeError):
        load_policy_from_file("test_policy.json")


@patch("luthien_control.new_control_policy.registry.POLICY_NAME_TO_CLASS", MOCK_REGISTRY)
@patch("builtins.open", side_effect=FileNotFoundError("File not found"))
def test_load_policy_from_file_file_not_found(mock_file):
    """Test loading fails when file does not exist."""
    with pytest.raises(FileNotFoundError):
        load_policy_from_file("nonexistent.json")