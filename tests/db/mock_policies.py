from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import httpx
from luthien_control.control_policy.serial_policy import SerialPolicy
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.core.types import ApiKeyLookupFunc
from luthien_control.settings import Settings

# --- Mock Policy Classes for Testing crud.py ---


class MockSimplePolicy(ControlPolicy):
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient, timeout: int = 30):
        self.settings = settings
        self.http_client = http_client
        self.timeout = timeout
        self.name: Optional[str] = None
        # Add mock_init for testing calls
        self.mock_init = MagicMock()
        # Call it to record the call
        self.mock_init(settings=settings, http_client=http_client, timeout=timeout)

    async def apply(self, context: Dict[str, Any], request_args: Dict[str, Any]) -> Dict[str, Any]:
        context["simple_applied"] = True
        context["simple_timeout"] = self.timeout
        return context

    def serialize(self) -> Dict[str, Any]:
        # In tests, we often manually set these, don\'t include them if None
        config = {"timeout": self.timeout}
        return config


class MockNestedPolicy(ControlPolicy):
    def __init__(self, nested_policy: ControlPolicy, description: str):
        self.nested_policy = nested_policy
        self.description = description
        self.name: Optional[str] = None
        # Add mock_init for testing calls
        self.mock_init = MagicMock()
        self.mock_init(nested_policy=nested_policy, description=description)

    async def apply(self, context: Dict[str, Any], request_args: Dict[str, Any]) -> Dict[str, Any]:
        context["nested_applied"] = True
        context["nested_description"] = self.description
        # Simulate applying inner policy using the updated attribute name
        context = await self.nested_policy.apply(context, request_args)
        return context

    def serialize(self) -> Dict[str, Any]:
        # In tests, we often manually set these, don\'t include them if None
        config = {
            "description": self.description,
            # Use the key the instantiator expects to find in config
            "nested_policy": self.nested_policy.serialize(),
        }
        return config


class MockListPolicy(ControlPolicy):
    def __init__(self, policies: List[Any], mode: str):
        # Accept list with mixed types as per test
        self.policies = policies
        self.mode = mode
        self.name: Optional[str] = None

    async def apply(self, context: Dict[str, Any], request_args: Dict[str, Any]) -> Dict[str, Any]:
        context["list_applied"] = True
        context["list_mode"] = self.mode
        context["list_policy_count"] = len(self.policies)
        # Simulate applying inner policies (simplified)
        for i, policy in enumerate(self.policies):
            if isinstance(policy, ControlPolicy):  # Skip non-policy items
                context[f"list_member_{i}_name"] = getattr(policy, "name", "unknown")
        return context

    def serialize(self) -> Dict[str, Any]:
        # Filter out non-policy items for serialization
        policy_configs = [p.serialize() for p in self.policies if isinstance(p, ControlPolicy)]
        config = {
            "mode": self.mode,
            "policies": policy_configs,
        }
        return config


class MockPolicyWithApiKeyLookup(ControlPolicy):
    def __init__(self, api_key_lookup: ApiKeyLookupFunc, tag: str):
        self.api_key_lookup = api_key_lookup
        self.tag = tag
        self.name: Optional[str] = None
        # Add mock_init for testing
        self.mock_init = MagicMock()
        self.mock_init(api_key_lookup=api_key_lookup, tag=tag)

    async def apply(self, context: Dict[str, Any], request_args: Dict[str, Any]) -> Dict[str, Any]:
        # Simulate using the lookup
        key = await self.api_key_lookup("test-key")
        context["lookup_applied"] = True
        context["lookup_tag"] = self.tag
        context["lookup_result_type"] = type(key).__name__
        return context

    def serialize(self) -> Dict[str, Any]:
        config = {"tag": self.tag}
        return config


class MockNoArgsPolicy(ControlPolicy):
    def __init__(self):
        self.name: Optional[str] = None
        # Add mock_init for testing
        self.mock_init = MagicMock()
        self.mock_init()

    async def apply(self, context: Dict[str, Any], request_args: Dict[str, Any]) -> Dict[str, Any]:
        context["no_args_applied"] = True
        return context

    def serialize(self) -> Dict[str, Any]:
        config = {}
        return config


class MockMissingArgPolicy(ControlPolicy):
    # Intentionally missing settings/http_client to test injection failure
    def __init__(self, mandatory: str):
        self.mandatory = mandatory
        self.name: Optional[str] = None

    async def apply(self, context: Dict[str, Any], request_args: Dict[str, Any]) -> Dict[str, Any]:
        context["missing_arg_applied"] = True
        context["missing_arg_mandatory"] = self.mandatory
        return context

    def serialize(self) -> Dict[str, Any]:
        config = {"mandatory": self.mandatory}
        return config


# Make it inherit from the real CompoundPolicy
class MockCompoundPolicy(SerialPolicy):
    """Mock policy mimicking CompoundPolicy structure, accepting a list of policies."""

    def __init__(self, policies: List[ControlPolicy], name: str = "default_compound"):
        super().__init__(policies=policies, name=name)

        # Add a mock_init for testing calls *after* super().__init__
        self.mock_init = MagicMock()
        # Call the mock_init to record the call with args passed to this mock's init
        self.mock_init(policies=policies, name=name)
