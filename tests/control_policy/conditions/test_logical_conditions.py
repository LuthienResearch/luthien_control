from typing import List

import httpx
import pytest
from luthien_control.control_policy.conditions.all_cond import AllCondition
from luthien_control.control_policy.conditions.any_cond import AnyCondition
from luthien_control.control_policy.conditions.comparisons import EqualsCondition  # For constructing test cases
from luthien_control.control_policy.conditions.condition import Condition
from luthien_control.control_policy.conditions.not_cond import NotCondition
from luthien_control.control_policy.conditions.util import get_condition_from_serialized  # For testing deserialization
from luthien_control.core.tracked_context import TrackedContext


@pytest.fixture
def true_condition() -> Condition:
    """A simple condition that always evaluates to True."""
    return EqualsCondition(key="data.static_true", value=True)


@pytest.fixture
def false_condition() -> Condition:
    """A simple condition that always evaluates to False."""
    return EqualsCondition(key="data.static_false", value=True)  # Note: data.static_false will be False in context


@pytest.fixture
def sample_request() -> httpx.Request:
    """Provides a sample httpx.Request object."""
    return httpx.Request(
        method="GET",
        url="http://example.com/test",
    )


@pytest.fixture
def sample_response() -> httpx.Response:
    """Provides a sample httpx.Response object."""
    return httpx.Response(
        status_code=200,
        json={"message": "ok"},
    )


@pytest.fixture
def transaction_context(sample_request: httpx.Request, sample_response: httpx.Response) -> TrackedContext:
    """Provides a TrackedContext populated with sample request, response, and static data for conditions."""
    context = TrackedContext()
    context.update_request(
        method=sample_request.method,
        url=str(sample_request.url),
        headers=dict(sample_request.headers),
        content=sample_request.content,
    )
    context.update_response(
        status_code=sample_response.status_code, headers=dict(sample_response.headers), content=sample_response.content
    )
    context.set_data("static_true", True)
    context.set_data("static_false", False)
    context.set_data("value_a", "hello")
    context.set_data("value_b", 10)
    return context


# Tests for AllCondition, AnyCondition, NotCondition will go here


# AllCondition Tests
@pytest.mark.parametrize(
    "conditions_setup, expected_result",
    [
        ([], True),  # Empty list evaluates to True
        (["true"], True),
        (["false"], False),
        (["true", "true"], True),
        (["false", "false"], False),
        (["true", "false"], False),
        (["true", "true", "false"], False),
    ],
)
def test_all_condition_evaluation(
    conditions_setup: List[str],
    expected_result: bool,
    transaction_context: TrackedContext,
    true_condition: Condition,
    false_condition: Condition,
) -> None:
    """Tests the evaluation logic for AllCondition."""
    conditions_map = {"true": true_condition, "false": false_condition}
    conditions = [conditions_map[cond_type] for cond_type in conditions_setup]
    all_cond = AllCondition(conditions)
    assert all_cond.evaluate(transaction_context) is expected_result


@pytest.mark.parametrize(
    "conditions_setup",
    [
        ([]),
        (["true"]),
        (["false"]),
        (["true", "false", "true"]),
    ],
)
def test_all_condition_serialization_deserialization(
    conditions_setup: List[str], true_condition: Condition, false_condition: Condition
) -> None:
    """Tests serialization and deserialization round-trip for AllCondition."""
    conditions_map = {"true": true_condition, "false": false_condition}
    conditions = [conditions_map[cond_type] for cond_type in conditions_setup]

    original_condition = AllCondition(conditions)
    serialized_data = original_condition.serialize()

    assert serialized_data["type"] == AllCondition.type
    # Ensure "conditions" is a list before using len() or indexing
    conditions_list = serialized_data["conditions"]
    assert isinstance(conditions_list, list)
    assert len(conditions_list) == len(conditions)
    for i, cond in enumerate(conditions):
        assert conditions_list[i] == cond.serialize()

    from_serializedd_condition = get_condition_from_serialized(serialized_data)
    assert isinstance(from_serializedd_condition, AllCondition)
    assert len(from_serializedd_condition.conditions) == len(original_condition.conditions)
    # For a more robust check, we'd ideally compare the structure of inner conditions too,
    # but that depends on their own serialize/from_serialized and equality implementations.
    # Here, we rely on the fact that get_condition_from_serialized handles this for us.
    # A simple re-serialization check can also be a good indicator:
    assert from_serializedd_condition.serialize() == serialized_data


# AnyCondition Tests
@pytest.mark.parametrize(
    "conditions_setup, expected_result",
    [
        ([], False),  # Empty list evaluates to False
        (["true"], True),
        (["false"], False),
        (["true", "true"], True),
        (["false", "false"], False),
        (["true", "false"], True),
        (["false", "false", "true"], True),
    ],
)
def test_any_condition_evaluation(
    conditions_setup: List[str],
    expected_result: bool,
    transaction_context: TrackedContext,
    true_condition: Condition,
    false_condition: Condition,
) -> None:
    """Tests the evaluation logic for AnyCondition."""
    conditions_map = {"true": true_condition, "false": false_condition}
    conditions = [conditions_map[cond_type] for cond_type in conditions_setup]
    any_cond = AnyCondition(conditions)
    assert any_cond.evaluate(transaction_context) is expected_result


@pytest.mark.parametrize(
    "conditions_setup",
    [
        ([]),
        (["true"]),
        (["false"]),
        (["true", "false", "true"]),
    ],
)
def test_any_condition_serialization_deserialization(
    conditions_setup: List[str], true_condition: Condition, false_condition: Condition
) -> None:
    """Tests serialization and deserialization round-trip for AnyCondition."""
    conditions_map = {"true": true_condition, "false": false_condition}
    conditions = [conditions_map[cond_type] for cond_type in conditions_setup]

    original_condition = AnyCondition(conditions)
    serialized_data = original_condition.serialize()

    assert serialized_data["type"] == AnyCondition.type
    # Ensure "conditions" is a list before using len() or indexing
    conditions_list = serialized_data["conditions"]
    assert isinstance(conditions_list, list)
    assert len(conditions_list) == len(conditions)
    for i, cond in enumerate(conditions):
        assert conditions_list[i] == cond.serialize()

    from_serializedd_condition = get_condition_from_serialized(serialized_data)
    assert isinstance(from_serializedd_condition, AnyCondition)
    assert len(from_serializedd_condition.conditions) == len(original_condition.conditions)
    assert from_serializedd_condition.serialize() == serialized_data


# NotCondition Tests
@pytest.mark.parametrize(
    "condition_type, expected_result",
    [
        ("true", False),
        ("false", True),
    ],
)
def test_not_condition_evaluation(
    condition_type: str,
    expected_result: bool,
    transaction_context: TrackedContext,
    true_condition: Condition,
    false_condition: Condition,
) -> None:
    """Tests the evaluation logic for NotCondition."""
    condition_map = {"true": true_condition, "false": false_condition}
    inner_condition = condition_map[condition_type]
    not_cond = NotCondition(inner_condition)
    assert not_cond.evaluate(transaction_context) is expected_result


@pytest.mark.parametrize(
    "condition_type",
    [
        ("true"),
        ("false"),
    ],
)
def test_not_condition_serialization_deserialization(
    condition_type: str, true_condition: Condition, false_condition: Condition
) -> None:
    """Tests serialization and deserialization round-trip for NotCondition."""
    condition_map = {"true": true_condition, "false": false_condition}
    inner_condition = condition_map[condition_type]

    original_condition = NotCondition(inner_condition)
    serialized_data = original_condition.serialize()

    assert serialized_data["type"] == NotCondition.type
    assert serialized_data["value"] == inner_condition.serialize()

    from_serializedd_condition = get_condition_from_serialized(serialized_data)
    assert isinstance(from_serializedd_condition, NotCondition)
    # Check that the inner condition was also correctly from_serializedd
    assert isinstance(from_serializedd_condition.cond, type(inner_condition))
    assert from_serializedd_condition.cond.serialize() == inner_condition.serialize()
    assert from_serializedd_condition.serialize() == serialized_data


def test_not_condition_from_serialized_invalid_value():
    """Test NotCondition.from_serialized with invalid 'value' field."""
    # Test with non-dict value
    invalid_serialized = {"type": "not", "value": "not_a_dict"}
    with pytest.raises(TypeError) as exc_info:
        NotCondition.from_serialized(invalid_serialized)  # type: ignore
    assert "must be a dictionary" in str(exc_info.value)
