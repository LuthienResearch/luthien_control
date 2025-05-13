import re

import pytest
from luthien_control.control_policy.conditions.comparators import (
    COMPARATOR_TO_NAME,
    NAME_TO_COMPARATOR,
    Comparator,
    contains,
    equals,
    greater_than,
    greater_than_or_equal,
    less_than,
    less_than_or_equal,
    regex_match,
)


def test_comparator_base_class():
    """Tests the base Comparator class."""
    comp = Comparator(lambda x, y: x == y)
    assert comp.evaluate(1, 1) is True
    assert comp.evaluate(1, 2) is False


def test_equals_comparator():
    """Tests the 'equals' comparator."""
    assert equals.evaluate(1, 1) is True
    assert equals.evaluate("a", "a") is True
    assert equals.evaluate([1, 2], [1, 2]) is True
    assert equals.evaluate({"a": 1}, {"a": 1}) is True

    assert equals.evaluate(1, 2) is False
    assert equals.evaluate("a", "b") is False
    assert equals.evaluate([1, 2], [2, 1]) is False
    assert equals.evaluate({"a": 1}, {"b": 1}) is False
    assert equals.evaluate(1, "1") is False


def test_contains_comparator():
    """Tests the 'contains' comparator."""
    assert contains.evaluate("a", "abc") is True  # string contains char
    assert contains.evaluate("ab", "abc") is True  # string contains substring
    assert contains.evaluate(1, [1, 2, 3]) is True  # list contains item
    assert contains.evaluate("a", {"a": 1, "b": 2}) is True  # dict contains key

    assert contains.evaluate("d", "abc") is False
    assert contains.evaluate("ac", "abc") is False  # substring order matters
    assert contains.evaluate(4, [1, 2, 3]) is False
    assert contains.evaluate("c", {"a": 1, "b": 2}) is False
    assert contains.evaluate([1], [1, 2, 3]) is False  # list does not contain sublist, just item


def test_less_than_comparator():
    """Tests the 'less_than' comparator."""
    assert less_than.evaluate(1, 2) is True
    assert less_than.evaluate(-1, 0) is True
    assert less_than.evaluate(1.0, 1.1) is True

    assert less_than.evaluate(2, 1) is False
    assert less_than.evaluate(1, 1) is False
    assert less_than.evaluate(1.1, 1.0) is False
    assert less_than.evaluate("a", "b") is True

    with pytest.raises(TypeError):
        less_than.evaluate(1, "1")


def test_less_than_or_equal_comparator():
    """Tests the 'less_than_or_equal' comparator."""
    assert less_than_or_equal.evaluate(1, 2) is True
    assert less_than_or_equal.evaluate(1, 1) is True
    assert less_than_or_equal.evaluate(-1, 0) is True
    assert less_than_or_equal.evaluate(1.0, 1.1) is True
    assert less_than_or_equal.evaluate(1.0, 1.0) is True

    assert less_than_or_equal.evaluate(2, 1) is False
    assert less_than_or_equal.evaluate(1.1, 1.0) is False
    assert less_than_or_equal.evaluate("b", "a") is False
    assert less_than_or_equal.evaluate("a", "a") is True

    with pytest.raises(TypeError):
        less_than_or_equal.evaluate(1, "1")


def test_greater_than_comparator():
    """Tests the 'greater_than' comparator."""
    assert greater_than.evaluate(2, 1) is True
    assert greater_than.evaluate(0, -1) is True
    assert greater_than.evaluate(1.1, 1.0) is True

    assert greater_than.evaluate(1, 2) is False
    assert greater_than.evaluate(1, 1) is False
    assert greater_than.evaluate(1.0, 1.1) is False
    assert greater_than.evaluate("b", "a") is True

    with pytest.raises(TypeError):
        greater_than.evaluate(1, "1")


def test_greater_than_or_equal_comparator():
    """Tests the 'greater_than_or_equal' comparator."""
    assert greater_than_or_equal.evaluate(2, 1) is True
    assert greater_than_or_equal.evaluate(1, 1) is True
    assert greater_than_or_equal.evaluate(0, -1) is True
    assert greater_than_or_equal.evaluate(1.1, 1.0) is True
    assert greater_than_or_equal.evaluate(1.0, 1.0) is True

    assert greater_than_or_equal.evaluate(1, 2) is False
    assert greater_than_or_equal.evaluate(1.0, 1.1) is False
    assert greater_than_or_equal.evaluate("a", "b") is False
    with pytest.raises(TypeError):
        greater_than_or_equal.evaluate(1, "1")


def test_regex_match_comparator():
    """Tests the 'regex_match' comparator."""
    assert regex_match.evaluate("abc", r"^a") is True
    assert regex_match.evaluate("abc", r"c$") is True
    assert regex_match.evaluate("abc", r"^abc$") is True
    assert regex_match.evaluate("abracadabra", r"a.r.c.d.b.a") is True

    assert regex_match.evaluate("abc", r"^b") is False
    assert regex_match.evaluate("abc", r"d$") is False
    assert regex_match.evaluate("abracadabra", r"^a.r.c.d.b.Z") is False

    # If we want to find abc anywhere, the pattern should be r".*abc"
    assert regex_match.evaluate("xabc", r".*abc") is True

    with pytest.raises(TypeError):
        regex_match.evaluate(123, r"\d+")
    with pytest.raises(re.error):  # Invalid regex pattern
        regex_match.evaluate("abc", r"[")


def test_name_to_comparator_mapping():
    """Tests the NAME_TO_COMPARATOR mapping."""
    assert NAME_TO_COMPARATOR["equals"] is equals
    assert NAME_TO_COMPARATOR["contains"] is contains
    assert NAME_TO_COMPARATOR["less_than"] is less_than
    assert NAME_TO_COMPARATOR["less_than_or_equal"] is less_than_or_equal
    assert NAME_TO_COMPARATOR["greater_than"] is greater_than
    assert NAME_TO_COMPARATOR["greater_than_or_equal"] is greater_than_or_equal
    assert NAME_TO_COMPARATOR["regex_match"] is regex_match

    # Check that all defined comparators are in the map
    defined_comparators = {
        equals,
        contains,
        less_than,
        less_than_or_equal,
        greater_than,
        greater_than_or_equal,
        regex_match,
    }
    assert set(NAME_TO_COMPARATOR.values()) == defined_comparators


def test_comparator_to_name_mapping():
    """Tests the COMPARATOR_TO_NAME mapping."""
    assert COMPARATOR_TO_NAME[equals] == "equals"
    assert COMPARATOR_TO_NAME[contains] == "contains"
    assert COMPARATOR_TO_NAME[less_than] == "less_than"
    assert COMPARATOR_TO_NAME[less_than_or_equal] == "less_than_or_equal"
    assert COMPARATOR_TO_NAME[greater_than] == "greater_than"
    assert COMPARATOR_TO_NAME[greater_than_or_equal] == "greater_than_or_equal"
    assert COMPARATOR_TO_NAME[regex_match] == "regex_match"

    # Check consistency between the two maps
    for name, comparator_obj in NAME_TO_COMPARATOR.items():
        assert COMPARATOR_TO_NAME[comparator_obj] == name

    assert len(NAME_TO_COMPARATOR) == len(COMPARATOR_TO_NAME)
