# pyright: reportCallIssue=false, reportAttributeAccessIssue=false, reportUnhashable=false
from typing import List

import pytest
from luthien_control.api.openai_chat_completions.datatypes import Choice, Message, Usage
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse
from luthien_control.control_policy.conditions import EqualsCondition, path
from luthien_control.control_policy.conditions.all_cond import AllCondition
from luthien_control.control_policy.conditions.any_cond import AnyCondition
from luthien_control.control_policy.conditions.condition import Condition
from luthien_control.control_policy.conditions.not_cond import NotCondition
from luthien_control.control_policy.conditions.util import get_condition_from_serialized
from luthien_control.core.request import Request
from luthien_control.core.response import Response
from luthien_control.core.transaction import Transaction
from psygnal.containers import EventedDict, EventedList


@pytest.fixture
def true_condition() -> Condition:
    """A simple condition that always evaluates to True."""
    return EqualsCondition(path("data.static_true"), True)


@pytest.fixture
def false_condition() -> Condition:
    """A simple condition that always evaluates to False."""
    return EqualsCondition(path("data.static_false"), True)  # Note: data.static_false will be False in transaction


@pytest.fixture
def sample_transaction() -> Transaction:
    """Provides a Transaction populated with sample request, response, and static data for conditions."""

    # Create request
    request = Request(
        payload=OpenAIChatCompletionsRequest(
            model="gpt-4",
            messages=EventedList([Message(role="user", content="Hello, world!")]),
        ),
        api_endpoint="https://api.openai.com/v1/chat/completions",
        api_key="test_key",
    )

    # Create response
    response = Response(
        payload=OpenAIChatCompletionsResponse(
            id="chatcmpl-123",
            object="chat.completion",
            created=1677652288,
            model="gpt-4",
            choices=EventedList(
                [
                    Choice(
                        index=0,
                        message=Message(role="assistant", content="Hello there!"),
                        finish_reason="stop",
                    )
                ]
            ),
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
    )

    # Create transaction with static data for condition testing
    transaction_data = EventedDict(
        {
            "static_true": True,
            "static_false": False,
            "value_a": "hello",
            "value_b": 10,
        }
    )

    transaction = Transaction(
        request=request,
        response=response,
        data=transaction_data,
    )

    return transaction


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
    sample_transaction: Transaction,
    true_condition: Condition,
    false_condition: Condition,
) -> None:
    """Tests the evaluation logic for AllCondition."""
    conditions_map = {"true": true_condition, "false": false_condition}
    conditions = [conditions_map[cond_type] for cond_type in conditions_setup]
    all_cond = AllCondition(conditions=conditions)
    assert all_cond.evaluate(sample_transaction) is expected_result


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

    original_condition = AllCondition(conditions=conditions)
    serialized_data = original_condition.serialize()

    assert serialized_data["type"] == "all"
    # Ensure "conditions" is a list before using len() or indexing
    conditions_list = serialized_data["conditions"]
    assert isinstance(conditions_list, list)
    assert len(conditions_list) == len(conditions)

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
    sample_transaction: Transaction,
    true_condition: Condition,
    false_condition: Condition,
) -> None:
    """Tests the evaluation logic for AnyCondition."""
    conditions_map = {"true": true_condition, "false": false_condition}
    conditions = [conditions_map[cond_type] for cond_type in conditions_setup]
    any_cond = AnyCondition(conditions=conditions)
    assert any_cond.evaluate(sample_transaction) is expected_result


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

    original_condition = AnyCondition(conditions=conditions)
    serialized_data = original_condition.serialize()

    assert serialized_data["type"] == "any"
    # Ensure "conditions" is a list before using len() or indexing
    conditions_list = serialized_data["conditions"]
    assert isinstance(conditions_list, list)
    assert len(conditions_list) == len(conditions)

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
    sample_transaction: Transaction,
    true_condition: Condition,
    false_condition: Condition,
) -> None:
    """Tests the evaluation logic for NotCondition."""
    condition_map = {"true": true_condition, "false": false_condition}
    inner_condition = condition_map[condition_type]
    not_cond = NotCondition(cond=inner_condition)
    assert not_cond.evaluate(sample_transaction) is expected_result


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

    original_condition = NotCondition(cond=inner_condition)
    serialized_data = original_condition.serialize()

    assert serialized_data["type"] == "not"
    assert "cond" in serialized_data

    from_serializedd_condition = get_condition_from_serialized(serialized_data)
    assert isinstance(from_serializedd_condition, NotCondition)
    # Check that the inner condition was also correctly from_serializedd
    assert isinstance(from_serializedd_condition.cond, type(inner_condition))
    assert from_serializedd_condition.cond.serialize() == inner_condition.serialize()
    assert from_serializedd_condition.serialize() == serialized_data


def test_not_condition_from_serialized_invalid_cond():
    """Test NotCondition.from_serialized with invalid 'cond' field."""
    # Test with non-dict cond
    invalid_serialized = {"type": "not", "cond": "not_a_dict"}
    with pytest.raises(TypeError) as exc_info:
        NotCondition.from_serialized(invalid_serialized)  # type: ignore
    assert "must be a dictionary" in str(exc_info.value)
