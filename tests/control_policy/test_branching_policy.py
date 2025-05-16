import json
from collections import OrderedDict
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from luthien_control.control_policy.branching_policy import BranchingPolicy
from luthien_control.control_policy.conditions.condition import Condition
from luthien_control.control_policy.conditions.registry import NAME_TO_CONDITION_CLASS
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.registry import POLICY_NAME_TO_CLASS
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.transaction_context import TransactionContext
from sqlalchemy.ext.asyncio import AsyncSession

# Mock implementations for Condition and ControlPolicy


class MockCondition(Condition):
    type = "mock_condition"

    def __init__(self, name: str, eval_result: bool):
        self.name = name
        self._eval_result = eval_result
        self.serialize_called = False
        self.evaluate_called_with = None

    def evaluate(self, context: TransactionContext) -> bool:
        self.evaluate_called_with = context
        return self._eval_result

    def serialize(self) -> SerializableDict:
        self.serialize_called = True
        return {"type": self.type, "name": self.name, "eval_result": self._eval_result}

    @classmethod
    def from_serialized(cls, serialized: SerializableDict) -> "MockCondition":
        name = serialized.get("name")
        eval_result = serialized.get("eval_result")
        if not isinstance(name, str):
            raise ValueError(f"MockCondition 'name' must be a string, got {type(name)}")
        if not isinstance(eval_result, bool):
            raise ValueError(f"MockCondition 'eval_result' must be a bool, got {type(eval_result)}")
        return cls(name=name, eval_result=eval_result)


class MockPolicy(ControlPolicy):
    type = "mock_policy"

    def __init__(self, name: str, **kwargs: Any):
        super().__init__(**kwargs)
        self.name = name
        self.apply_called_with = None
        self.serialize_called = False
        self.config_from_load = None

    async def apply(
        self, context: TransactionContext, container: DependencyContainer, session: AsyncSession
    ) -> TransactionContext:
        self.apply_called_with = (context, container, session)
        modified_context = TransactionContext(data={"applied_policy": self.name, **context.data})
        return modified_context

    def serialize(self) -> SerializableDict:
        self.serialize_called = True
        data: SerializableDict = {"type": self.type}
        if self.name is not None:
            data["name"] = self.name
        return data

    @classmethod
    def from_serialized(cls, config: SerializableDict, **kwargs: Any) -> "MockPolicy":
        name = config.get("name")
        if not isinstance(name, str):
            name = cls.type
        instance = cls(name=name, **kwargs)
        instance.config_from_load = config
        return instance


@pytest.fixture
def mock_context() -> TransactionContext:
    return TransactionContext(data={"initial_key": "initial_value"})


@pytest.fixture
def mock_container() -> DependencyContainer:
    return MagicMock(spec=DependencyContainer)


@pytest.fixture
def mock_session() -> AsyncMock:
    return AsyncMock(spec=AsyncSession)


@pytest.fixture(autouse=True)
def patch_registries():
    with (
        patch.dict(POLICY_NAME_TO_CLASS, {MockPolicy.type: MockPolicy}, clear=True) as patched_policies,
        patch.dict(NAME_TO_CONDITION_CLASS, {MockCondition.type: MockCondition}, clear=True) as patched_conditions,
    ):
        patched_policies[BranchingPolicy.__name__] = BranchingPolicy
        yield patched_policies, patched_conditions


@pytest.mark.asyncio
async def test_apply_first_condition_matches(
    mock_context: TransactionContext, mock_container: DependencyContainer, mock_session: AsyncMock
):
    """Test that the first matching condition's policy is applied."""
    cond1 = MockCondition(name="cond1", eval_result=True)
    policy1 = MockPolicy(name="policy1")
    cond2 = MockCondition(name="cond2", eval_result=False)  # Should not be evaluated
    policy2 = MockPolicy(name="policy2")

    cond_to_policy_map: OrderedDict[Condition, ControlPolicy] = OrderedDict([(cond1, policy1), (cond2, policy2)])
    branching_policy = BranchingPolicy(cond_to_policy_map)

    result_context = await branching_policy.apply(mock_context, mock_container, mock_session)

    assert cond1.evaluate_called_with == mock_context
    assert policy1.apply_called_with is not None
    assert cond2.evaluate_called_with is None  # cond2 should not be evaluated
    assert policy2.apply_called_with is None
    assert result_context.data.get("applied_policy") == "policy1"
    assert result_context.data.get("initial_key") == "initial_value"


@pytest.mark.asyncio
async def test_apply_second_condition_matches(
    mock_context: TransactionContext, mock_container: DependencyContainer, mock_session: AsyncMock
):
    """Test that if the first condition doesn't match, the second one is tried."""
    cond1 = MockCondition(name="cond1", eval_result=False)
    policy1 = MockPolicy(name="policy1")
    cond2 = MockCondition(name="cond2", eval_result=True)
    policy2 = MockPolicy(name="policy2")

    cond_to_policy_map: OrderedDict[Condition, ControlPolicy] = OrderedDict([(cond1, policy1), (cond2, policy2)])
    branching_policy = BranchingPolicy(cond_to_policy_map)

    result_context = await branching_policy.apply(mock_context, mock_container, mock_session)

    assert cond1.evaluate_called_with == mock_context
    assert policy1.apply_called_with is None
    assert cond2.evaluate_called_with == mock_context
    assert policy2.apply_called_with is not None
    assert result_context.data.get("applied_policy") == "policy2"


@pytest.mark.asyncio
async def test_apply_no_condition_matches_default_policy_applied(
    mock_context: TransactionContext, mock_container: DependencyContainer, mock_session: AsyncMock
):
    """Test that the default policy is applied if no conditions match."""
    cond1 = MockCondition(name="cond1", eval_result=False)
    policy1 = MockPolicy(name="policy1")
    cond2 = MockCondition(name="cond2", eval_result=False)
    policy2 = MockPolicy(name="policy2")
    default_policy = MockPolicy(name="default_policy")

    cond_to_policy_map: OrderedDict[Condition, ControlPolicy] = OrderedDict([(cond1, policy1), (cond2, policy2)])
    branching_policy = BranchingPolicy(cond_to_policy_map, default_policy=default_policy)

    result_context = await branching_policy.apply(mock_context, mock_container, mock_session)

    assert cond1.evaluate_called_with == mock_context
    assert policy1.apply_called_with is None
    assert cond2.evaluate_called_with == mock_context
    assert policy2.apply_called_with is None
    assert default_policy.apply_called_with is not None
    assert result_context.data.get("applied_policy") == "default_policy"


@pytest.mark.asyncio
async def test_apply_no_condition_matches_no_default_policy(
    mock_context: TransactionContext, mock_container: DependencyContainer, mock_session: AsyncMock
):
    """Test that the original context is returned if no conditions match and no default policy."""
    cond1 = MockCondition(name="cond1", eval_result=False)
    policy1 = MockPolicy(name="policy1")
    cond2 = MockCondition(name="cond2", eval_result=False)
    policy2 = MockPolicy(name="policy2")

    cond_to_policy_map: OrderedDict[Condition, ControlPolicy] = OrderedDict([(cond1, policy1), (cond2, policy2)])
    branching_policy = BranchingPolicy(cond_to_policy_map, default_policy=None)

    result_context = await branching_policy.apply(mock_context, mock_container, mock_session)

    assert cond1.evaluate_called_with == mock_context
    assert policy1.apply_called_with is None
    assert cond2.evaluate_called_with == mock_context
    assert policy2.apply_called_with is None
    assert result_context == mock_context  # Original context should be returned
    assert result_context.data.get("applied_policy") is None


def test_serialize_with_default_policy():
    """Test serialization when a default policy is present."""
    cond1 = MockCondition(name="cond1", eval_result=True)
    policy1 = MockPolicy(name="policy1")
    default_policy = MockPolicy(name="default_policy")

    cond_to_policy_map: OrderedDict[Condition, ControlPolicy] = OrderedDict([(cond1, policy1)])
    branching_policy = BranchingPolicy(cond_to_policy_map, default_policy=default_policy, name="TestBranch")

    serialized_data = branching_policy.serialize()

    assert cond1.serialize_called
    assert policy1.serialize_called
    assert default_policy.serialize_called

    expected_cond_key = json.dumps(cond1.serialize())

    expected_serialization = {
        "type": "branching",
        "cond_to_policy_map": {expected_cond_key: policy1.serialize()},
        "default_policy": default_policy.serialize(),
    }
    assert serialized_data["type"] == "branching"

    cond_map_serialized = serialized_data.get("cond_to_policy_map")
    assert isinstance(cond_map_serialized, dict)
    assert list(cond_map_serialized.keys()) == [expected_cond_key]
    assert cond_map_serialized[expected_cond_key] == policy1.serialize()
    assert serialized_data["default_policy"] == expected_serialization["default_policy"]


def test_serialize_without_default_policy():
    """Test serialization when no default policy is present."""
    cond1 = MockCondition(name="cond1", eval_result=True)
    policy1 = MockPolicy(name="policy1")

    cond_to_policy_map: OrderedDict[Condition, ControlPolicy] = OrderedDict([(cond1, policy1)])
    branching_policy = BranchingPolicy(cond_to_policy_map, default_policy=None)

    serialized_data = branching_policy.serialize()

    assert cond1.serialize_called
    assert policy1.serialize_called

    expected_cond_key = json.dumps(cond1.serialize())

    {
        "type": "branching",
        "cond_to_policy_map": {expected_cond_key: policy1.serialize()},
        "default_policy": None,
    }
    assert serialized_data["type"] == "branching"

    cond_map_serialized = serialized_data.get("cond_to_policy_map")
    assert isinstance(cond_map_serialized, dict)
    assert list(cond_map_serialized.keys()) == [expected_cond_key]
    assert cond_map_serialized[expected_cond_key] == policy1.serialize()
    assert serialized_data["default_policy"] is None


def test_from_serialized_with_default_policy(patch_registries):
    cond1_serialized_inner = {"type": MockCondition.type, "name": "cond1_deserialized", "eval_result": True}
    policy1_serialized = {"type": MockPolicy.type, "name": "policy1_deserialized"}
    default_policy_serialized = {"type": MockPolicy.type, "name": "default_deserialized"}

    cond1_key_str = json.dumps(cond1_serialized_inner)

    serialized_config = {
        "type": "BranchingPolicy",
        "cond_to_policy_map": {cond1_key_str: policy1_serialized},
        "default_policy": default_policy_serialized,
    }

    branching_policy = BranchingPolicy.from_serialized(serialized_config)

    assert isinstance(branching_policy, BranchingPolicy)
    assert len(branching_policy.cond_to_policy_map) == 1

    deserialized_cond = None
    deserialized_policy = None
    for cond, policy_obj in branching_policy.cond_to_policy_map.items():
        if isinstance(cond, MockCondition) and cond.name == "cond1_deserialized":
            deserialized_cond = cond
            deserialized_policy = policy_obj
            break

    assert deserialized_cond is not None
    assert deserialized_cond.name == "cond1_deserialized"
    assert deserialized_cond._eval_result

    assert deserialized_policy is not None
    assert isinstance(deserialized_policy, MockPolicy)
    assert deserialized_policy.name == "policy1_deserialized"

    assert isinstance(branching_policy.default_policy, MockPolicy)
    assert branching_policy.default_policy.name == "default_deserialized"


def test_from_serialized_without_default_policy(patch_registries):
    cond1_serialized_inner = {"type": MockCondition.type, "name": "cond_no_default", "eval_result": False}
    policy1_serialized = {"type": MockPolicy.type, "name": "policy_no_default"}

    cond1_key_str = json.dumps(cond1_serialized_inner)

    serialized_config = {
        "cond_to_policy_map": {cond1_key_str: policy1_serialized},
        "default_policy": None,
    }

    branching_policy = BranchingPolicy.from_serialized(serialized_config)

    assert isinstance(branching_policy, BranchingPolicy)
    assert len(branching_policy.cond_to_policy_map) == 1

    deserialized_cond = None
    deserialized_policy = None
    for cond, policy_obj in branching_policy.cond_to_policy_map.items():
        if isinstance(cond, MockCondition) and cond.name == "cond_no_default":
            deserialized_cond = cond
            deserialized_policy = policy_obj
            break

    assert deserialized_cond is not None
    assert deserialized_cond.name == "cond_no_default"
    assert not deserialized_cond._eval_result

    assert deserialized_policy is not None
    assert isinstance(deserialized_policy, MockPolicy)
    assert deserialized_policy.name == "policy_no_default"

    assert branching_policy.default_policy is None
