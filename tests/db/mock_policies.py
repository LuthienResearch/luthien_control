from typing import Any, Dict, List, Optional

import httpx

from luthien_control.config.settings import Settings
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.db.crud import ApiKeyLookupFunc


# --- Mock Policy Classes for Testing crud.py ---


class MockSimplePolicy(ControlPolicy):
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient, timeout: int = 30):
        self.settings = settings
        self.http_client = http_client
        self.timeout = timeout
        self.name: Optional[str] = None
        self.policy_class_path: Optional[str] = None

    async def apply(self, context: Dict[str, Any], request_args: Dict[str, Any]) -> Dict[str, Any]:
        context["simple_applied"] = True
        context["simple_timeout"] = self.timeout
        return context

    def serialize_config(self) -> Dict[str, Any]:
        # In tests, we often manually set these, don\'t include them if None
        config = {"timeout": self.timeout}
        # if self.name: config[\"name\"] = self.name
        # if self.policy_class_path: config[\"policy_class_path\"] = self.policy_class_path
        return config


class MockNestedPolicy(ControlPolicy):
    def __init__(self, inner_policy: ControlPolicy, description: str):
        self.inner_policy = inner_policy
        self.description = description
        self.name: Optional[str] = None
        self.policy_class_path: Optional[str] = None

    async def apply(self, context: Dict[str, Any], request_args: Dict[str, Any]) -> Dict[str, Any]:
        context["nested_applied"] = True
        context["nested_description"] = self.description
        # Simulate applying inner policy
        context = await self.inner_policy.apply(context, request_args)
        return context

    def serialize_config(self) -> Dict[str, Any]:
        # In tests, we often manually set these, don\'t include them if None
        config = {
            "description": self.description,
            "inner_policy": self.inner_policy.serialize_config(),  # Assumes inner serializes
        }
        # if self.name: config[\"name\"] = self.name
        # if self.policy_class_path: config[\"policy_class_path\"] = self.policy_class_path
        return config


class MockListPolicy(ControlPolicy):
    def __init__(self, policies: List[Any], mode: str):
        # Accept list with mixed types as per test
        self.policies = policies
        self.mode = mode
        self.name: Optional[str] = None
        self.policy_class_path: Optional[str] = None

    async def apply(self, context: Dict[str, Any], request_args: Dict[str, Any]) -> Dict[str, Any]:
        context["list_applied"] = True
        context["list_mode"] = self.mode
        context["list_policy_count"] = len(self.policies)
        # Simulate applying inner policies (simplified)
        for i, policy in enumerate(self.policies):
            if isinstance(policy, ControlPolicy):  # Skip non-policy items
                context[f"list_member_{i}_name"] = getattr(policy, "name", "unknown")
                # context = await policy.apply(context, request_args) # Defer actual application
        return context

    def serialize_config(self) -> Dict[str, Any]:
        # Filter out non-policy items for serialization
        policy_configs = [p.serialize_config() for p in self.policies if isinstance(p, ControlPolicy)]
        # Keep non-policy items as-is in config per test expectations?
        # Let\'s just serialize policies for now.
        config = {
            "mode": self.mode,
            "policies": policy_configs,
        }
        # if self.name: config[\"name\"] = self.name
        # if self.policy_class_path: config[\"policy_class_path\"] = self.policy_class_path
        return config


class MockPolicyWithApiKeyLookup(ControlPolicy):
    def __init__(self, api_key_lookup: ApiKeyLookupFunc, tag: str):
        self.api_key_lookup = api_key_lookup
        self.tag = tag
        self.name: Optional[str] = None
        self.policy_class_path: Optional[str] = None

    async def apply(self, context: Dict[str, Any], request_args: Dict[str, Any]) -> Dict[str, Any]:
        # Simulate using the lookup
        key = await self.api_key_lookup("test-key")
        context["lookup_applied"] = True
        context["lookup_tag"] = self.tag
        context["lookup_result_type"] = type(key).__name__
        return context

    def serialize_config(self) -> Dict[str, Any]:
        config = {"tag": self.tag}
        # if self.name: config[\"name\"] = self.name
        # if self.policy_class_path: config[\"policy_class_path\"] = self.policy_class_path
        return config


class MockNoArgsPolicy(ControlPolicy):
    def __init__(self):
        self.name: Optional[str] = None
        self.policy_class_path: Optional[str] = None

    async def apply(self, context: Dict[str, Any], request_args: Dict[str, Any]) -> Dict[str, Any]:
        context["no_args_applied"] = True
        return context

    def serialize_config(self) -> Dict[str, Any]:
        config = {}
        # if self.name: config[\"name\"] = self.name
        # if self.policy_class_path: config[\"policy_class_path\"] = self.policy_class_path
        return config


class MockMissingArgPolicy(ControlPolicy):
    # Intentionally missing settings/http_client to test injection failure
    def __init__(self, mandatory: str):
        self.mandatory = mandatory
        self.name: Optional[str] = None
        self.policy_class_path: Optional[str] = None

    async def apply(self, context: Dict[str, Any], request_args: Dict[str, Any]) -> Dict[str, Any]:
        context["missing_arg_applied"] = True
        context["missing_arg_mandatory"] = self.mandatory
        return context

    def serialize_config(self) -> Dict[str, Any]:
        config = {"mandatory": self.mandatory}
        # if self.name: config[\"name\"] = self.name
        # if self.policy_class_path: config[\"policy_class_path\"] = self.policy_class_path
        return config
