"""Tests for BranchingPolicy."""
# pyright: reportCallIssue=false

import json
from collections import OrderedDict
from typing import Any, Dict, cast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from luthien_control.api.openai_chat_completions.datatypes import Choice, Message, Usage
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse
from luthien_control.control_policy.branching_policy import BranchingPolicy
from luthien_control.control_policy.conditions import EqualsCondition, path
from luthien_control.control_policy.conditions.condition import Condition
from luthien_control.control_policy.conditions.registry import NAME_TO_CONDITION_CLASS
from luthien_control.control_policy.control_policy import ControlPolicy
from luthien_control.control_policy.noop_policy import NoopPolicy
from luthien_control.control_policy.registry import POLICY_NAME_TO_CLASS
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.request import Request
from luthien_control.core.response import Response
from luthien_control.core.transaction import Transaction
from psygnal.containers import EventedDict, EventedList
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

# --- Test Fixtures and Helper Classes ---


class MockSimplePolicy(ControlPolicy):
    """Simple test policy that sets a marker in the transaction data."""

    marker: str

    @classmethod
    def get_policy_type_name(cls) -> str:
        """Override to avoid registry lookup for test class."""
        return "MockSimplePolicy"

    async def apply(
        self, transaction: Transaction, container: DependencyContainer, session: AsyncSession
    ) -> Transaction:
        # Set a marker in the transaction data to track which policy was applied
        if transaction.data is None:
            transaction.data = EventedDict()
        transaction.data["applied_policy"] = self.marker
        return transaction

    @classmethod
    def from_serialized(cls, config: SerializableDict) -> "MockSimplePolicy":
        """Custom from_serialized to handle missing name field for backward compatibility."""
        config_copy = dict(config)
        if "name" not in config_copy:
            config_copy["name"] = cls.__name__
        return super().from_serialized(config_copy)

    def __repr__(self) -> str:
        return f"<MockSimplePolicy(marker={self.marker!r})>"


@pytest.fixture
def sample_transaction() -> Transaction:
    """Provides a Transaction for testing."""
    request = Request(
        payload=OpenAIChatCompletionsRequest(
            model="gpt-4",
            messages=EventedList([Message(role="user", content="Hello, world!")]),
        ),
        api_endpoint="https://api.openai.com/v1/chat/completions",
        api_key="test_key",
    )

    response = Response(
        payload=OpenAIChatCompletionsResponse(
            id="chatcmpl-123",
            object="chat.completion",
            created=1677652288,
            model="gpt-4",
            choices=EventedList(
                [Choice(index=0, message=Message(role="assistant", content="Hello there!"), finish_reason="stop")]
            ),
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
    )

    transaction_data = EventedDict(
        {
            "method": "GET",
            "user_type": "admin",
        }
    )

    return Transaction(request=request, response=response, data=transaction_data)


@pytest.fixture
def mock_container() -> MagicMock:
    """Provides a mock dependency container."""
    return MagicMock()


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Provides a mock database session."""
    return AsyncMock()


# --- Test Cases ---


@pytest.mark.parametrize(
    "condition_values,expected_policy",
    [
        # First condition matches (GET method)
        ([("data.method", "GET"), ("data.user_type", "admin")], "policy1"),
        # Second condition matches (POST method, but user_type admin)
        ([("data.method", "POST"), ("data.user_type", "admin")], "policy2"),
    ],
)
@pytest.mark.asyncio
async def test_branching_policy_condition_matching(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
    condition_values: list[tuple[str, str]],
    expected_policy: str,
):
    """Test that the correct policy is applied based on condition matching order."""
    cond1 = EqualsCondition(path(condition_values[0][0]), condition_values[0][1])
    cond2 = EqualsCondition(path(condition_values[1][0]), condition_values[1][1])

    policy1 = MockSimplePolicy(marker="policy1")
    policy2 = MockSimplePolicy(marker="policy2")

    policy_map = cast(OrderedDict[Condition, ControlPolicy], OrderedDict([(cond1, policy1), (cond2, policy2)]))

    branching_policy = BranchingPolicy(cond_to_policy_map=policy_map)

    result = await branching_policy.apply(sample_transaction, mock_container, mock_db_session)

    assert result is sample_transaction
    assert result.data is not None
    assert result.data["applied_policy"] == expected_policy


@pytest.mark.asyncio
async def test_branching_policy_no_conditions_match_with_default(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that default policy is applied when no conditions match."""
    cond1 = EqualsCondition(path("data.method"), "POST")  # Won't match GET
    policy1 = MockSimplePolicy(marker="policy1")
    default_policy = MockSimplePolicy(marker="default")

    policy_map = cast(OrderedDict[Condition, ControlPolicy], OrderedDict([(cond1, policy1)]))

    branching_policy = BranchingPolicy(cond_to_policy_map=policy_map, default_policy=default_policy)

    result = await branching_policy.apply(sample_transaction, mock_container, mock_db_session)

    assert result is sample_transaction
    assert result.data is not None
    assert result.data["applied_policy"] == "default"


@pytest.mark.asyncio
async def test_branching_policy_no_conditions_match_no_default(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that original transaction is returned when no conditions match and no default."""
    cond1 = EqualsCondition(path("data.method"), "POST")  # Won't match GET
    policy1 = MockSimplePolicy(marker="policy1")

    policy_map = cast(OrderedDict[Condition, ControlPolicy], OrderedDict([(cond1, policy1)]))

    branching_policy = BranchingPolicy(cond_to_policy_map=policy_map)

    # Store original state
    assert sample_transaction.data is not None
    original_data = dict(sample_transaction.data)

    result = await branching_policy.apply(sample_transaction, mock_container, mock_db_session)

    assert result is sample_transaction
    # Should not have "applied_policy" since no policy was applied
    assert result.data is not None
    assert "applied_policy" not in result.data
    # Other data should be unchanged
    assert result.data["method"] == original_data["method"]
    assert result.data["user_type"] == original_data["user_type"]


@pytest.mark.asyncio
async def test_branching_policy_empty_condition_map(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test BranchingPolicy with empty condition map."""
    default_policy = MockSimplePolicy(marker="default")

    policy_map = cast(OrderedDict[Condition, ControlPolicy], OrderedDict())
    branching_policy = BranchingPolicy(cond_to_policy_map=policy_map, default_policy=default_policy)

    result = await branching_policy.apply(sample_transaction, mock_container, mock_db_session)

    assert result is sample_transaction
    assert result.data is not None
    assert result.data["applied_policy"] == "default"


@pytest.mark.asyncio
async def test_branching_policy_policy_exception_propagates(
    sample_transaction: Transaction,
    mock_container: MagicMock,
    mock_db_session: AsyncMock,
):
    """Test that exceptions from applied policies propagate correctly."""

    class ExceptionPolicy(ControlPolicy):
        @classmethod
        def get_policy_type_name(cls) -> str:
            """Override to avoid registry lookup for test class."""
            return "ExceptionPolicy"

        async def apply(
            self, transaction: Transaction, container: DependencyContainer, session: AsyncSession
        ) -> Transaction:
            raise ValueError("Policy failed")

    cond1 = EqualsCondition(path("data.method"), "GET")  # This will match
    exception_policy = ExceptionPolicy()

    policy_map = cast(OrderedDict[Condition, ControlPolicy], OrderedDict([(cond1, exception_policy)]))

    branching_policy = BranchingPolicy(cond_to_policy_map=policy_map)

    with pytest.raises(ValueError, match="Policy failed"):
        await branching_policy.apply(sample_transaction, mock_container, mock_db_session)


@pytest.mark.parametrize(
    "name,expected_name",
    [
        ("CustomBranching", "CustomBranching"),
        (None, "BranchingPolicy"),  # Now uses default class name instead of None
    ],
)
def test_branching_policy_initialization_name(name: str | None, expected_name: str | None):
    """Test BranchingPolicy initialization with and without name."""
    cond = EqualsCondition(path("data.test"), "value")
    policy = NoopPolicy()
    policy_map = cast(OrderedDict[Condition, ControlPolicy], OrderedDict([(cond, policy)]))

    branching_policy = (
        BranchingPolicy(cond_to_policy_map=policy_map, name=name)
        if name
        else BranchingPolicy(cond_to_policy_map=policy_map)
    )

    assert branching_policy.name == expected_name


def test_branching_policy_serialize_with_default_policy_and_name():
    """Test BranchingPolicy serialization with default policy and name."""
    cond = EqualsCondition(path("data.method"), "GET")
    policy = NoopPolicy(name="TestPolicy")
    default_policy = NoopPolicy(name="DefaultPolicy")
    policy_map = cast(OrderedDict[Condition, ControlPolicy], OrderedDict([(cond, policy)]))

    branching_policy = BranchingPolicy(
        cond_to_policy_map=policy_map, default_policy=default_policy, name="TestBranching"
    )
    serialized = branching_policy.serialize()

    assert serialized["type"] == "BranchingPolicy"
    assert serialized["name"] == "TestBranching"
    assert serialized["default_policy"] == default_policy.serialize()

    # Check condition mapping
    cond_map = serialized["cond_to_policy_map"]
    assert isinstance(cond_map, dict)
    assert len(cond_map) == 1
    cond_key = list(cond_map.keys())[0]
    assert json.loads(cond_key) == cond.serialize()
    assert cond_map[cond_key] == policy.serialize()


def test_branching_policy_serialize_without_default_policy_and_name():
    """Test BranchingPolicy serialization without default policy and name."""
    cond = EqualsCondition(path("data.method"), "GET")
    policy = NoopPolicy(name="TestPolicy")
    policy_map = cast(OrderedDict[Condition, ControlPolicy], OrderedDict([(cond, policy)]))

    branching_policy = BranchingPolicy(cond_to_policy_map=policy_map)
    serialized = branching_policy.serialize()

    assert serialized["type"] == "BranchingPolicy"
    assert serialized["name"] == "BranchingPolicy"  # Now includes default class name
    assert serialized["default_policy"] is None

    # Check condition mapping
    cond_map = serialized["cond_to_policy_map"]
    assert isinstance(cond_map, dict)
    assert len(cond_map) == 1


def test_branching_policy_serialize_multiple_conditions():
    """Test BranchingPolicy serialization with multiple conditions."""
    cond1 = EqualsCondition(path("data.method"), "GET")
    cond2 = EqualsCondition(path("data.user_type"), "admin")
    policy1 = NoopPolicy(name="Policy1")
    policy2 = NoopPolicy(name="Policy2")

    policy_map = cast(OrderedDict[Condition, ControlPolicy], OrderedDict([(cond1, policy1), (cond2, policy2)]))
    branching_policy = BranchingPolicy(cond_to_policy_map=policy_map)

    serialized = branching_policy.serialize()

    cond_map = serialized["cond_to_policy_map"]
    assert isinstance(cond_map, dict)
    assert len(cond_map) == 2

    # Check both conditions are present
    condition_jsons = list(cond_map.keys())
    deserialized_conditions = [json.loads(cj) for cj in condition_jsons]

    assert cond1.serialize() in deserialized_conditions
    assert cond2.serialize() in deserialized_conditions


def test_branching_policy_from_serialized_valid():
    """Test BranchingPolicy deserialization with valid config."""
    config = {
        "cond_to_policy_map": {
            json.dumps(
                {
                    "type": "equals",
                    "left": {"type": "transaction_path", "path": "data.method"},
                    "right": {"type": "static", "value": "GET"},
                    "comparator": "equals",
                }
            ): {
                "name": "TestPolicy",
                "type": "NoopPolicy",
            }
        },
        "default_policy": {"name": "DefaultPolicy", "type": "NoopPolicy"},
        "name": "TestBranching",
    }

    with (
        patch.dict(NAME_TO_CONDITION_CLASS, {"equals": EqualsCondition}),
        patch.dict(POLICY_NAME_TO_CLASS, {"NoopPolicy": NoopPolicy}),
    ):
        branching_policy = BranchingPolicy.from_serialized(config)

    assert branching_policy.name == "TestBranching"
    assert len(branching_policy.cond_to_policy_map) == 1
    assert branching_policy.default_policy is not None
    assert isinstance(branching_policy.default_policy, NoopPolicy)


def test_branching_policy_from_serialized_without_default():
    """Test BranchingPolicy deserialization without default policy."""
    config = {
        "cond_to_policy_map": {
            json.dumps(
                {
                    "type": "equals",
                    "left": {"type": "transaction_path", "path": "data.method"},
                    "right": {"type": "static", "value": "GET"},
                    "comparator": "equals",
                }
            ): {
                "name": "TestPolicy",
                "type": "NoopPolicy",
            }
        },
        "default_policy": None,
    }

    with (
        patch.dict(NAME_TO_CONDITION_CLASS, {"equals": EqualsCondition}),
        patch.dict(POLICY_NAME_TO_CLASS, {"NoopPolicy": NoopPolicy}),
    ):
        branching_policy = BranchingPolicy.from_serialized(config)

    assert branching_policy.name == "BranchingPolicy"  # Now uses default class name
    assert len(branching_policy.cond_to_policy_map) == 1
    assert branching_policy.default_policy is None


def test_branching_policy_from_serialized_without_name():
    """Test BranchingPolicy deserialization without name."""
    config = {"cond_to_policy_map": {}, "default_policy": None}

    branching_policy = BranchingPolicy.from_serialized(config)

    assert branching_policy.name == "BranchingPolicy"  # Now uses default class name
    assert len(branching_policy.cond_to_policy_map) == 0
    assert branching_policy.default_policy is None


def test_branching_policy_round_trip_serialization():
    """Test BranchingPolicy serialization and deserialization round trip."""
    cond = EqualsCondition(path("data.method"), "GET")
    policy = NoopPolicy(name="TestPolicy")
    default_policy = NoopPolicy(name="DefaultPolicy")

    policy_map = cast(OrderedDict[Condition, ControlPolicy], OrderedDict([(cond, policy)]))
    original = BranchingPolicy(cond_to_policy_map=policy_map, default_policy=default_policy, name="TestBranching")

    # Serialize
    serialized = original.serialize()

    # Deserialize
    with (
        patch.dict(NAME_TO_CONDITION_CLASS, {"equals": EqualsCondition}),
        patch.dict(POLICY_NAME_TO_CLASS, {"NoopPolicy": NoopPolicy}),
    ):
        restored = BranchingPolicy.from_serialized(serialized)

    # Verify
    assert restored.name == original.name
    assert len(restored.cond_to_policy_map) == len(original.cond_to_policy_map)
    assert restored.default_policy is not None
    assert isinstance(restored.default_policy, NoopPolicy)


# Error condition tests


def test_branching_policy_from_serialized_invalid_cond_to_policy_map_type():
    """Test BranchingPolicy deserialization with invalid cond_to_policy_map type."""
    config = cast(SerializableDict, {"cond_to_policy_map": "not_a_dict"})

    with pytest.raises(TypeError, match="Expected 'cond_to_policy_map' to be a dict"):
        BranchingPolicy.from_serialized(config)


def test_branching_policy_from_serialized_invalid_condition_key_type():
    """Test BranchingPolicy deserialization with invalid condition key type."""
    config = cast(SerializableDict, {"cond_to_policy_map": {123: {"type": "NoopPolicy", "name": "test"}}})

    with pytest.raises(TypeError, match="Condition key.*must be a JSON string"):
        BranchingPolicy.from_serialized(config)


def test_branching_policy_from_serialized_invalid_policy_config_type():
    """Test BranchingPolicy deserialization with invalid policy config type."""
    config = cast(
        SerializableDict, {"cond_to_policy_map": {'{"type": "equals", "key": "test", "value": "value"}': "not_a_dict"}}
    )

    with pytest.raises(TypeError, match="Policy config.*must be a dict"):
        BranchingPolicy.from_serialized(config)


def test_branching_policy_from_serialized_invalid_json():
    """Test BranchingPolicy deserialization with invalid JSON in condition key."""
    config = cast(SerializableDict, {"cond_to_policy_map": {"{invalid json": {"type": "NoopPolicy", "name": "test"}}})

    with pytest.raises(ValueError, match="Failed to parse condition JSON string"):
        BranchingPolicy.from_serialized(config)


def test_branching_policy_from_serialized_non_dict_condition():
    """Test BranchingPolicy deserialization with non-dict deserialized condition."""
    config = cast(SerializableDict, {"cond_to_policy_map": {'"just_a_string"': {"type": "NoopPolicy", "name": "test"}}})

    with pytest.raises(TypeError, match="Deserialized condition config.*must be a dict"):
        BranchingPolicy.from_serialized(config)


def test_branching_policy_from_serialized_invalid_default_policy_type():
    """Test BranchingPolicy deserialization with invalid default_policy type."""
    config = cast(SerializableDict, {"cond_to_policy_map": {}, "default_policy": "not_a_dict"})

    with pytest.raises(TypeError, match="Expected 'default_policy' config to be a dict"):
        BranchingPolicy.from_serialized(config)


def test_branching_policy_from_serialized_invalid_name_type():
    """Test BranchingPolicy deserialization with invalid name type."""
    config = cast(SerializableDict, {"cond_to_policy_map": {}, "default_policy": None, "name": 123})

    with pytest.raises(ValidationError, match="Input should be a valid string"):
        BranchingPolicy.from_serialized(config)


def test_branching_policy_serialize_unknown_policy_type():
    """Test BranchingPolicy serialization with mock policy type."""
    cond = EqualsCondition(path("data.method"), "GET")
    unknown_policy = MockSimplePolicy(marker="unknown")  # Mock policy with custom type name

    policy_map = cast(OrderedDict[Condition, ControlPolicy], OrderedDict([(cond, unknown_policy)]))
    branching_policy = BranchingPolicy(cond_to_policy_map=policy_map)

    serialized = branching_policy.serialize()
    assert serialized["type"] == "BranchingPolicy"
    assert "cond_to_policy_map" in serialized


def test_branching_policy_serialize_unknown_default_policy_type():
    """Test BranchingPolicy serialization with mock default policy type."""
    unknown_policy = MockSimplePolicy(marker="unknown")  # Mock policy with custom type name

    policy_map = cast(OrderedDict[Condition, ControlPolicy], OrderedDict())
    branching_policy = BranchingPolicy(cond_to_policy_map=policy_map, default_policy=unknown_policy)

    serialized = branching_policy.serialize()
    assert serialized["type"] == "BranchingPolicy"
    default_policy = cast(Dict[str, Any], serialized["default_policy"])
    assert default_policy["type"] == "MockSimplePolicy"
