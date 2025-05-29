import json
from collections import OrderedDict
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from luthien_control.control_policy.branching_policy import BranchingPolicy
from luthien_control.control_policy.conditions.comparisons import EqualsCondition
from luthien_control.control_policy.conditions.condition import Condition
from luthien_control.control_policy.conditions.registry import NAME_TO_CONDITION_CLASS
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.registry import POLICY_NAME_TO_CLASS
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction_context import TransactionContext
from sqlalchemy.ext.asyncio import AsyncSession


class SimplePolicy(ControlPolicy):
    """Simple test policy that sets a marker in the context."""

    def __init__(self, marker: str, **kwargs: Any):
        super().__init__(**kwargs)
        self.marker = marker

    async def apply(
        self, context: TransactionContext, container: DependencyContainer, session: AsyncSession
    ) -> TransactionContext:
        new_data = context.data.copy()
        new_data["applied_policy"] = self.marker
        return TransactionContext(data=new_data)

    def serialize(self) -> SerializableDict:
        return {"type": "SimplePolicy", "marker": self.marker}

    @classmethod
    def from_serialized(cls, config: SerializableDict, **kwargs: Any) -> "SimplePolicy":
        marker = config.get("marker")
        if not isinstance(marker, str):
            raise ValueError(f"SimplePolicy 'marker' must be a string, got {type(marker)}")
        return cls(marker=marker, **kwargs)


@pytest.fixture
def context() -> TransactionContext:
    return TransactionContext(data={"method": "GET", "user_type": "admin"})


@pytest.fixture
def mock_deps() -> tuple[DependencyContainer, AsyncSession]:
    return AsyncMock(spec=DependencyContainer), AsyncMock(spec=AsyncSession)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "first_matches,expected_policy",
    [
        (True, "policy1"),  # First condition matches
        (False, "policy2"),  # Second condition matches
    ],
)
async def test_policy_application_order(context, mock_deps, first_matches, expected_policy):
    """Test that policies are applied in correct order based on condition evaluation."""
    container, session = mock_deps

    cond1 = EqualsCondition(key="data.method", value="GET" if first_matches else "POST")
    cond2 = EqualsCondition(key="data.user_type", value="admin")

    policy_map = cast(
        OrderedDict[Condition, ControlPolicy],
        OrderedDict([(cond1, SimplePolicy("policy1")), (cond2, SimplePolicy("policy2"))]),
    )
    branching_policy = BranchingPolicy(policy_map)

    result = await branching_policy.apply(context, container, session)
    assert result.data["applied_policy"] == expected_policy


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "has_default,expected_policy",
    [
        (True, "default"),  # Default policy applied
        (False, None),  # No policy applied, original context returned
    ],
)
async def test_no_conditions_match(context, mock_deps, has_default, expected_policy):
    """Test behavior when no conditions match."""
    container, session = mock_deps

    cond = EqualsCondition(key="data.method", value="POST")  # Won't match GET
    policy_map = cast(OrderedDict[Condition, ControlPolicy], OrderedDict([(cond, SimplePolicy("policy1"))]))
    default_policy = SimplePolicy("default") if has_default else None

    branching_policy = BranchingPolicy(policy_map, default_policy=default_policy)
    result = await branching_policy.apply(context, container, session)

    if expected_policy:
        assert result.data["applied_policy"] == expected_policy
    else:
        assert result == context
        assert "applied_policy" not in result.data


@pytest.mark.parametrize("has_default", [True, False])
def test_serialization(has_default):
    """Test serialization with and without default policy."""
    cond = EqualsCondition(key="test", value="value")
    policy = SimplePolicy(marker="test_policy")
    default_policy = SimplePolicy(marker="default") if has_default else None

    branching_policy = BranchingPolicy(
        cast(OrderedDict[Condition, ControlPolicy], OrderedDict([(cond, policy)])), default_policy=default_policy
    )
    serialized = branching_policy.serialize()

    assert serialized["type"] == "branching"
    assert serialized["default_policy"] == (default_policy.serialize() if default_policy is not None else None)

    # Verify condition mapping
    cond_map = cast(dict[str, Any], serialized["cond_to_policy_map"])
    assert len(cond_map) == 1
    cond_key = list(cond_map.keys())[0]
    assert json.loads(cond_key) == cond.serialize()


@pytest.mark.parametrize("has_default,has_name", [(True, False), (False, False), (True, True)])
def test_deserialization_success(has_default, has_name):
    """Test successful deserialization scenarios."""
    cond = EqualsCondition(key="method", value="GET")
    policy = SimplePolicy(marker="test_policy")
    default_policy = SimplePolicy(marker="default") if has_default else None
    name = "test_branching" if has_name else None

    original = BranchingPolicy(
        cast(OrderedDict[Condition, ControlPolicy], OrderedDict([(cond, policy)])),
        default_policy=default_policy,
        name=name,
    )
    serialized = original.serialize()

    with (
        patch.dict(NAME_TO_CONDITION_CLASS, {"equals": EqualsCondition}),
        patch.dict(POLICY_NAME_TO_CLASS, {"SimplePolicy": SimplePolicy}),
    ):
        reconstructed = BranchingPolicy.from_serialized(serialized)

    assert len(reconstructed.cond_to_policy_map) == 1
    assert (reconstructed.default_policy is not None) == has_default
    assert reconstructed.name == name
    assert reconstructed.serialize() == serialized


@pytest.mark.parametrize(
    "invalid_config,expected_error,error_match",
    [
        # Invalid cond_to_policy_map type
        ({"cond_to_policy_map": "not_a_dict"}, TypeError, "Expected 'cond_to_policy_map' to be a dict"),
        # Invalid condition key type
        (
            {"cond_to_policy_map": {123: {"type": "SimplePolicy", "marker": "test"}}},
            TypeError,
            "Condition key.*must be a JSON string",
        ),
        # Invalid policy config type
        (
            {"cond_to_policy_map": {'{"type": "equals", "key": "test", "value": "value"}': "not_a_dict"}},
            TypeError,
            "Policy config.*must be a dict",
        ),
        # Invalid JSON in condition key
        (
            {"cond_to_policy_map": {"{invalid json": {"type": "SimplePolicy", "marker": "test"}}},
            ValueError,
            "Failed to parse condition JSON string",
        ),
        # Non-dict deserialized condition
        (
            {"cond_to_policy_map": {'"just_a_string"': {"type": "SimplePolicy", "marker": "test"}}},
            TypeError,
            "Deserialized condition config.*must be a dict",
        ),
        # Invalid default_policy type
        (
            {"cond_to_policy_map": {}, "default_policy": "not_a_dict"},
            TypeError,
            "Expected 'default_policy' config to be a dict",
        ),
        # Invalid name type
        (
            {"cond_to_policy_map": {}, "default_policy": None, "name": 123},
            TypeError,
            "BranchingPolicy name must be a string",
        ),
    ],
)
def test_deserialization_errors(invalid_config, expected_error, error_match):
    """Test various deserialization error conditions."""
    with pytest.raises(expected_error, match=error_match):
        BranchingPolicy.from_serialized(invalid_config)
