import pytest
from luthien_control.control_policy.conditions import EqualsCondition, path
from luthien_control.control_policy.conditions.all_cond import AllCondition
from luthien_control.control_policy.conditions.any_cond import AnyCondition
from luthien_control.control_policy.conditions.condition import Condition
from luthien_control.control_policy.conditions.not_cond import NotCondition
from luthien_control.control_policy.conditions.registry import (
    NAME_TO_CONDITION_CLASS,
)
from luthien_control.control_policy.conditions.util import (
    get_condition_class,
    get_condition_class_from_serialized,
    get_condition_from_serialized,
    get_conditions_from_serialized,
    get_transaction_value,
)
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.transaction import Transaction


def test_get_condition_class_valid() -> None:
    """Tests get_condition_class with valid condition names."""
    assert get_condition_class("equals") is EqualsCondition
    assert get_condition_class("all") is AllCondition
    assert get_condition_class("any") is AnyCondition
    assert get_condition_class("not") is NotCondition


def test_get_condition_class_invalid() -> None:
    """Tests get_condition_class with an invalid condition name."""
    with pytest.raises(KeyError):
        get_condition_class("invalid_condition_type")


def test_get_condition_class_from_serialized() -> None:
    """Tests get_condition_class_from_serialized."""
    serialized_equals: SerializableDict = {"type": "equals", "key": "foo", "value": "bar"}
    assert get_condition_class_from_serialized(serialized_equals) is EqualsCondition

    serialized_all: SerializableDict = {"type": "all", "conditions": []}
    assert get_condition_class_from_serialized(serialized_all) is AllCondition


@pytest.mark.parametrize(
    "condition_type_str, condition_class",
    [
        ("equals", EqualsCondition),
        ("not", NotCondition),
        ("all", AllCondition),
        ("any", AnyCondition),
    ],
)
def test_get_condition_from_serialized_simple_cases(condition_type_str: str, condition_class: type[Condition]) -> None:
    """Tests get_condition_from_serialized for simple, non-nested conditions."""
    # Create minimal valid serialized data for each type
    serialized_data: SerializableDict
    original_condition: Condition

    if condition_class == EqualsCondition:
        original_condition = EqualsCondition(path("test.key"), "test_value")
    elif condition_class == NotCondition:
        original_condition = NotCondition(cond=EqualsCondition(path("inner.key"), 1))
    elif condition_class == AllCondition:
        original_condition = AllCondition(conditions=[EqualsCondition(path("all.key1"), True)])
    elif condition_class == AnyCondition:
        original_condition = AnyCondition(conditions=[EqualsCondition(path("any.key1"), False)])
    else:
        pytest.fail(f"Unhandled condition class in test setup: {condition_class}")

    serialized_data = original_condition.serialize()
    # Double check type field to be sure
    assert serialized_data["type"] == condition_type_str

    from_serializedd_cond = get_condition_from_serialized(serialized_data)
    assert isinstance(from_serializedd_cond, condition_class)
    assert from_serializedd_cond.serialize() == serialized_data  # Check full reconstruction


def test_get_condition_from_serialized_nested() -> None:
    """Tests get_condition_from_serialized with nested conditions."""
    eq_cond1 = EqualsCondition(path("data.x"), 10)
    eq_cond2 = EqualsCondition(path("request.method"), "POST")
    not_cond = NotCondition(cond=eq_cond1)
    all_cond = AllCondition(conditions=[not_cond, eq_cond2])
    any_cond = AnyCondition(conditions=[all_cond, eq_cond1])

    original_conditions = [eq_cond1, eq_cond2, not_cond, all_cond, any_cond]

    for original_condition in original_conditions:
        serialized_data = original_condition.serialize()
        from_serializedd_condition = get_condition_from_serialized(serialized_data)
        assert isinstance(from_serializedd_condition, type(original_condition))
        assert from_serializedd_condition.serialize() == serialized_data


def test_get_conditions_from_serialized() -> None:
    """Tests get_conditions_from_serialized with default key."""
    eq_cond1_s = EqualsCondition(path("k1"), "v1").serialize()
    eq_cond2_s = EqualsCondition(path("k2"), "v2").serialize()
    serialized_input: SerializableDict = {"conditions": [eq_cond1_s, eq_cond2_s]}

    from_serializedd_list = get_conditions_from_serialized(serialized_input)
    assert len(from_serializedd_list) == 2
    assert isinstance(from_serializedd_list[0], EqualsCondition)
    assert isinstance(from_serializedd_list[1], EqualsCondition)
    assert from_serializedd_list[0].serialize() == eq_cond1_s
    assert from_serializedd_list[1].serialize() == eq_cond2_s


def test_get_conditions_from_serialized_custom_key() -> None:
    """Tests get_conditions_from_serialized with a custom key."""
    eq_cond_s = EqualsCondition(path("k"), "v").serialize()
    serialized_input: SerializableDict = {"my_custom_key": [eq_cond_s]}

    from_serializedd_list = get_conditions_from_serialized(serialized_input, key="my_custom_key")
    assert len(from_serializedd_list) == 1
    assert isinstance(from_serializedd_list[0], EqualsCondition)
    assert from_serializedd_list[0].serialize() == eq_cond_s


def test_get_conditions_from_serialized_empty_list() -> None:
    """Tests get_conditions_from_serialized with an empty list of conditions."""
    serialized_input: SerializableDict = {"conditions": []}
    from_serializedd_list = get_conditions_from_serialized(serialized_input)
    assert len(from_serializedd_list) == 0


def test_get_conditions_from_serialized_key_not_found() -> None:
    """Tests get_conditions_from_serialized when the key is not found."""
    serialized_input: SerializableDict = {"other_key": []}
    with pytest.raises(KeyError):
        get_conditions_from_serialized(serialized_input)


def test_all_conditions_registered() -> None:
    """Ensure all known condition types are in NAME_TO_CONDITION_CLASS for completeness."""
    # Add any new condition classes here to ensure they are registered.
    expected_condition_classes = {
        EqualsCondition,
        NotCondition,  # From comparisons
        # GreaterThanCondition, # etc. from comparisons, but not directly used in util's core logic.
        # We are more interested in the logical ones here for util tests.
        AllCondition,
        AnyCondition,
        # NotCondition is already listed
    }
    # Check that all expected types are values in the registry
    registered_classes = set(NAME_TO_CONDITION_CLASS.values())
    for cond_cls in expected_condition_classes:
        assert cond_cls in registered_classes, f"{cond_cls.__name__} is not registered in NAME_TO_CONDITION_CLASS"

    # Also check that all string keys correctly map back to these types
    for type_str, cond_cls in NAME_TO_CONDITION_CLASS.items():
        if cond_cls in expected_condition_classes:  # Only check relevant ones for this test scope
            assert get_condition_class(type_str) is cond_cls


def test_get_conditions_from_serialized_reraises_key_error() -> None:
    """Tests that get_conditions_from_serialized re-raises KeyError from line 27."""
    serialized_input: SerializableDict = {"other_key": []}
    with pytest.raises(KeyError):
        get_conditions_from_serialized(serialized_input)


def _create_minimal_transaction() -> Transaction:
    """Create a minimal transaction for testing."""
    from luthien_control.api.openai_chat_completions.datatypes import Message
    from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
    from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse
    from luthien_control.core.request import Request
    from luthien_control.core.response import Response
    from psygnal.containers import EventedList

    request = Request(
        payload=OpenAIChatCompletionsRequest(
            model="gpt-4",
            messages=EventedList([Message(role="user", content="test")]),
        ),
        api_endpoint="https://api.openai.com/v1/chat/completions",
        api_key="test",
    )

    response = Response(
        payload=OpenAIChatCompletionsResponse(
            id="test",
            object="chat.completion",
            created=1,
            model="gpt-4",
        )
    )

    return Transaction(request=request, response=response)


def test_get_transaction_value_short_path() -> None:
    """Tests get_transaction_value with a path that's too short."""
    transaction = _create_minimal_transaction()

    with pytest.raises(ValueError, match="Path must contain at least two components"):
        get_transaction_value(transaction, "single")


def test_get_transaction_value_attribute_error() -> None:
    """Tests get_transaction_value when attribute access fails."""
    transaction = _create_minimal_transaction()

    # This should raise AttributeError because 'nonexistent' doesn't exist on transaction
    with pytest.raises(AttributeError):
        get_transaction_value(transaction, "nonexistent.key")


def test_get_transaction_value_key_error_then_attribute_error() -> None:
    """Tests get_transaction_value when dict access fails then attribute access fails."""
    from psygnal.containers import EventedDict

    transaction = _create_minimal_transaction()

    # Set up data so it has dict-like access but will fail on key lookup
    transaction.data = EventedDict({"existing_key": "value"})

    # This should try dict access first, fail, then try attribute access, fail
    with pytest.raises(AttributeError, match="Cannot access 'nonexistent' on"):
        get_transaction_value(transaction, "data.nonexistent")


def test_get_transaction_value_index_access_failure() -> None:
    """Tests get_transaction_value when index access fails."""
    from psygnal.containers import EventedDict

    transaction = _create_minimal_transaction()

    # Set up a list that we'll try to access with an invalid index
    transaction.data = EventedDict({"items": ["item1", "item2"]})

    # This should fail when trying to access index 5 on a 2-item list
    with pytest.raises(AttributeError, match="Cannot access '5' on"):
        get_transaction_value(transaction, "data.items.5")
