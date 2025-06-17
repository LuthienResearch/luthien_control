import pytest
from luthien_control.control_policy.conditions.all_cond import AllCondition
from luthien_control.control_policy.conditions.any_cond import AnyCondition
from luthien_control.control_policy.conditions.comparisons import EqualsCondition
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
)
from luthien_control.control_policy.serialization import SerializableDict


def test_get_condition_class_valid() -> None:
    """Tests get_condition_class with valid condition names."""
    assert get_condition_class(EqualsCondition.type) is EqualsCondition
    assert get_condition_class(AllCondition.type) is AllCondition
    assert get_condition_class(AnyCondition.type) is AnyCondition
    assert get_condition_class(NotCondition.type) is NotCondition


def test_get_condition_class_invalid() -> None:
    """Tests get_condition_class with an invalid condition name."""
    with pytest.raises(KeyError):
        get_condition_class("invalid_condition_type")


def test_get_condition_class_from_serialized() -> None:
    """Tests get_condition_class_from_serialized."""
    serialized_equals: SerializableDict = {"type": EqualsCondition.type, "key": "foo", "value": "bar"}
    assert get_condition_class_from_serialized(serialized_equals) is EqualsCondition

    serialized_all: SerializableDict = {"type": AllCondition.type, "conditions": []}
    assert get_condition_class_from_serialized(serialized_all) is AllCondition


@pytest.mark.parametrize(
    "condition_type_str, condition_class",
    [
        (EqualsCondition.type, EqualsCondition),
        (NotCondition.type, NotCondition),
        (AllCondition.type, AllCondition),
        (AnyCondition.type, AnyCondition),
    ],
)
def test_get_condition_from_serialized_simple_cases(condition_type_str: str, condition_class: type[Condition]) -> None:
    """Tests get_condition_from_serialized for simple, non-nested conditions."""
    # Create minimal valid serialized data for each type
    serialized_data: SerializableDict
    original_condition: Condition

    if condition_class == EqualsCondition:
        original_condition = EqualsCondition(key="test.key", value="test_value")
    elif condition_class == NotCondition:
        original_condition = NotCondition(EqualsCondition(key="inner.key", value=1))
    elif condition_class == AllCondition:
        original_condition = AllCondition(conditions=[EqualsCondition(key="all.key1", value=True)])
    elif condition_class == AnyCondition:
        original_condition = AnyCondition(conditions=[EqualsCondition(key="any.key1", value=False)])
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
    eq_cond1 = EqualsCondition(key="data.x", value=10)
    eq_cond2 = EqualsCondition(key="request.method", value="POST")
    not_cond = NotCondition(value=eq_cond1)
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
    eq_cond1_s = EqualsCondition(key="k1", value="v1").serialize()
    eq_cond2_s = EqualsCondition(key="k2", value="v2").serialize()
    serialized_input: SerializableDict = {"conditions": [eq_cond1_s, eq_cond2_s]}

    from_serializedd_list = get_conditions_from_serialized(serialized_input)
    assert len(from_serializedd_list) == 2
    assert isinstance(from_serializedd_list[0], EqualsCondition)
    assert isinstance(from_serializedd_list[1], EqualsCondition)
    assert from_serializedd_list[0].serialize() == eq_cond1_s
    assert from_serializedd_list[1].serialize() == eq_cond2_s


def test_get_conditions_from_serialized_custom_key() -> None:
    """Tests get_conditions_from_serialized with a custom key."""
    eq_cond_s = EqualsCondition(key="k", value="v").serialize()
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
