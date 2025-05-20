from typing import Any, Optional, cast
from unittest.mock import patch

import pytest
from luthien_control.control_policy.exceptions import PolicyLoadError
from luthien_control.control_policy.loader import load_policy
from luthien_control.control_policy.serialization import SerializableDict, SerializedPolicy

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


@pytest.mark.asyncio
@patch("luthien_control.control_policy.registry.POLICY_NAME_TO_CLASS", MOCK_REGISTRY)
async def test_load_policy_success():
    """Test successful loading of a known policy type."""
    serialized_policy_data = {"type": "mock_policy", "config": {"key": "value", "name": "instance_one"}}
    serialized_policy_obj = SerializedPolicy(
        type=serialized_policy_data["type"], config=serialized_policy_data["config"]
    )
    policy = load_policy(serialized_policy_obj)

    assert isinstance(policy, MockPolicy)
    assert policy.config == {"key": "value", "name": "instance_one"}
    assert policy.name == "instance_one"  # Name set from config


@pytest.mark.asyncio
@patch("luthien_control.control_policy.registry.POLICY_NAME_TO_CLASS", MOCK_REGISTRY)
async def test_load_policy_success_no_name_in_config():
    """Test successful loading when name is not in config (uses class default)."""
    serialized_policy_data = {"type": "mock_policy", "config": {"key": "value"}}
    serialized_policy_obj = SerializedPolicy(
        type=serialized_policy_data["type"], config=serialized_policy_data["config"]
    )
    policy = load_policy(serialized_policy_obj)

    assert isinstance(policy, MockPolicy)
    assert policy.config == {"key": "value"}
    assert policy.name == "mock_policy"  # Default name from class


@pytest.mark.asyncio
@patch("luthien_control.control_policy.registry.POLICY_NAME_TO_CLASS", MOCK_REGISTRY)
async def test_load_policy_unknown_type():
    """Test loading fails for an unknown policy type."""
    serialized_policy_data = {"type": "unknown_policy", "config": {}}
    serialized_policy_obj = SerializedPolicy(
        type=serialized_policy_data["type"], config=serialized_policy_data["config"]
    )

    with pytest.raises(PolicyLoadError, match="Unknown policy type: 'unknown_policy'"):
        load_policy(serialized_policy_obj)


@patch("luthien_control.control_policy.registry.POLICY_NAME_TO_CLASS", MOCK_REGISTRY)
def test_load_policy_instantiation_error():
    """Test loading fails when the policy's from_serialized raises an error."""
    serialized_policy_data = {
        "type": "mock_policy",
        "config": {"fail_load": True},  # Instruct mock to fail
    }
    serialized_policy_obj = SerializedPolicy(
        type=serialized_policy_data["type"], config=serialized_policy_data["config"]
    )

    with pytest.raises(PolicyLoadError, match="Error instantiating policy 'mock_policy'"):
        load_policy(serialized_policy_obj)


@pytest.mark.asyncio
@patch("luthien_control.control_policy.registry.POLICY_NAME_TO_CLASS", MOCK_REGISTRY)
async def test_load_policy_invalid_type_format():
    """Test loading fails if 'type' is not a string."""
    policy_type_val: Any = 123
    policy_config_val: SerializableDict = {}

    serialized_policy_obj = SerializedPolicy(type=policy_type_val, config=policy_config_val)

    with pytest.raises(PolicyLoadError, match="Policy 'type' must be a string"):
        load_policy(serialized_policy_obj)


@pytest.mark.asyncio
@patch("luthien_control.control_policy.registry.POLICY_NAME_TO_CLASS", MOCK_REGISTRY)
async def test_load_policy_invalid_config_format():
    """Test loading fails if 'config' is not a dictionary."""
    policy_type_val: str = "mock_policy"
    policy_config_val: Any = "not_a_dict"

    serialized_policy_obj = SerializedPolicy(type=policy_type_val, config=policy_config_val)

    with pytest.raises(PolicyLoadError, match="Policy 'config' must be a dictionary"):
        load_policy(serialized_policy_obj)
