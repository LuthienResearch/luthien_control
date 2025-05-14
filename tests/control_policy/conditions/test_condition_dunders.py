import pytest
from luthien_control.control_policy.conditions.all_cond import AllCondition
from luthien_control.control_policy.conditions.any_cond import AnyCondition
from luthien_control.control_policy.conditions.comparisons import (
    ContainsCondition,
    EqualsCondition,
    GreaterThanCondition,
    GreaterThanOrEqualCondition,
    LessThanCondition,
    LessThanOrEqualCondition,
    NotEqualsCondition,
    RegexMatchCondition,
)
from luthien_control.control_policy.conditions.condition import Condition
from luthien_control.control_policy.conditions.not_cond import NotCondition


class TestEqualsConditionDunders:
    """Tests for __repr__, __eq__, and __hash__ on EqualsCondition."""

    def test_repr(self) -> None:
        """Tests the __repr__ method of EqualsCondition."""
        cond = EqualsCondition(key="request.method", value="GET")
        expected_repr = "EqualsCondition(key='request.method', value='GET')"
        assert repr(cond) == expected_repr

    def test_eq(self) -> None:
        """Tests the __eq__ method of EqualsCondition."""
        cond1a = EqualsCondition(key="request.method", value="GET")
        cond1b = EqualsCondition(key="request.method", value="GET")  # Identical
        cond2_diff_value = EqualsCondition(key="request.method", value="POST")  # Different value
        cond3_diff_key = EqualsCondition(key="response.status", value="GET")  # Different key

        assert cond1a == cond1b, "Identical instances should be equal"
        assert cond1a != cond2_diff_value, "Instances with different values should not be equal"
        assert cond1a != cond3_diff_key, "Instances with different keys should not be equal"
        assert cond1a != "some_other_type", "Instance should not be equal to a string"

        # Test against a different ComparisonCondition type
        # The base Condition.__eq__ checks isinstance(other, self.__class__),
        # so this will be false.
        other_comp_cond = NotEqualsCondition(key="request.method", value="GET")
        assert cond1a != other_comp_cond, "EqualsCondition should not be equal to NotEqualsCondition"

        # Test against a non-ComparisonCondition type (logical condition)
        # For this, we need a simple logical condition instance
        dummy_logical_cond = NotCondition(value=EqualsCondition(key="dummy", value=True))
        assert cond1a != dummy_logical_cond, "EqualsCondition should not be equal to NotCondition"

    def test_hash(self) -> None:
        """Tests the __hash__ method of EqualsCondition."""
        cond1a = EqualsCondition(key="request.method", value="GET")
        cond1b = EqualsCondition(key="request.method", value="GET")
        cond2_diff_value = EqualsCondition(key="request.method", value="POST")

        assert hash(cond1a) == hash(cond1b), "Hashes of identical instances should be equal"

        # Test usability in a set
        s = {cond1a, cond1b, cond2_diff_value}
        assert len(s) == 2, "Set should contain 2 unique elements"
        assert cond1a in s, "cond1a should be in the set"
        assert cond2_diff_value in s, "cond2_diff_value should be in the set"


class TestNotEqualsConditionDunders:
    """Tests for __repr__, __eq__, and __hash__ on NotEqualsCondition."""

    def test_repr(self) -> None:
        """Tests the __repr__ method of NotEqualsCondition."""
        cond = NotEqualsCondition(key="request.method", value="GET")
        expected_repr = "NotEqualsCondition(key='request.method', value='GET')"
        assert repr(cond) == expected_repr

    def test_eq(self) -> None:
        """Tests the __eq__ method of NotEqualsCondition."""
        cond1a = NotEqualsCondition(key="request.method", value="GET")
        cond1b = NotEqualsCondition(key="request.method", value="GET")
        cond2_diff_value = NotEqualsCondition(key="request.method", value="POST")
        cond3_diff_key = NotEqualsCondition(key="response.status", value="GET")

        assert cond1a == cond1b
        assert cond1a != cond2_diff_value
        assert cond1a != cond3_diff_key
        assert cond1a != "some_other_type"
        other_comp_cond = EqualsCondition(key="request.method", value="GET")
        assert cond1a != other_comp_cond

    def test_hash(self) -> None:
        """Tests the __hash__ method of NotEqualsCondition."""
        cond1a = NotEqualsCondition(key="request.method", value="GET")
        cond1b = NotEqualsCondition(key="request.method", value="GET")
        cond2_diff_value = NotEqualsCondition(key="request.method", value="POST")

        assert hash(cond1a) == hash(cond1b)
        s = {cond1a, cond1b, cond2_diff_value}
        assert len(s) == 2
        assert cond1a in s
        assert cond2_diff_value in s


class TestContainsConditionDunders:
    """Tests for __repr__, __eq__, and __hash__ on ContainsCondition."""

    def test_repr(self) -> None:
        """Tests the __repr__ method of ContainsCondition."""
        cond = ContainsCondition(key="request.headers.accept", value="application/json")
        expected_repr = "ContainsCondition(key='request.headers.accept', value='application/json')"
        assert repr(cond) == expected_repr

    def test_eq(self) -> None:
        """Tests the __eq__ method of ContainsCondition."""
        cond1a = ContainsCondition(key="request.headers.accept", value="application/json")
        cond1b = ContainsCondition(key="request.headers.accept", value="application/json")
        cond2_diff_value = ContainsCondition(key="request.headers.accept", value="text/html")
        cond3_diff_key = ContainsCondition(key="response.body", value="application/json")

        assert cond1a == cond1b
        assert cond1a != cond2_diff_value
        assert cond1a != cond3_diff_key
        assert cond1a != "some_other_type"
        other_comp_cond = EqualsCondition(key="request.headers.accept", value="application/json")
        assert cond1a != other_comp_cond

    def test_hash(self) -> None:
        """Tests the __hash__ method of ContainsCondition."""
        cond1a = ContainsCondition(key="request.headers.accept", value="application/json")
        cond1b = ContainsCondition(key="request.headers.accept", value="application/json")
        cond2_diff_value = ContainsCondition(key="request.headers.accept", value="text/html")

        assert hash(cond1a) == hash(cond1b)
        s = {cond1a, cond1b, cond2_diff_value}
        assert len(s) == 2
        assert cond1a in s
        assert cond2_diff_value in s


class TestLessThanConditionDunders:
    """Tests for __repr__, __eq__, and __hash__ on LessThanCondition."""

    def test_repr(self) -> None:
        cond = LessThanCondition(key="response.latency_ms", value=100)
        expected_repr = "LessThanCondition(key='response.latency_ms', value=100)"
        assert repr(cond) == expected_repr

    def test_eq(self) -> None:
        cond1a = LessThanCondition(key="response.latency_ms", value=100)
        cond1b = LessThanCondition(key="response.latency_ms", value=100)
        cond2_diff_value = LessThanCondition(key="response.latency_ms", value=200)
        cond3_diff_key = LessThanCondition(key="request.retries", value=100)

        assert cond1a == cond1b
        assert cond1a != cond2_diff_value
        assert cond1a != cond3_diff_key
        assert cond1a != "some_other_type"
        other_comp_cond = GreaterThanCondition(key="response.latency_ms", value=100)
        assert cond1a != other_comp_cond

    def test_hash(self) -> None:
        cond1a = LessThanCondition(key="response.latency_ms", value=100)
        cond1b = LessThanCondition(key="response.latency_ms", value=100)
        cond2_diff_value = LessThanCondition(key="response.latency_ms", value=200)

        assert hash(cond1a) == hash(cond1b)
        s = {cond1a, cond1b, cond2_diff_value}
        assert len(s) == 2
        assert cond1a in s
        assert cond2_diff_value in s


class TestLessThanOrEqualConditionDunders:
    """Tests for __repr__, __eq__, and __hash__ on LessThanOrEqualCondition."""

    def test_repr(self) -> None:
        cond = LessThanOrEqualCondition(key="user.age", value=65)
        expected_repr = "LessThanOrEqualCondition(key='user.age', value=65)"
        assert repr(cond) == expected_repr

    def test_eq(self) -> None:
        cond1a = LessThanOrEqualCondition(key="user.age", value=65)
        cond1b = LessThanOrEqualCondition(key="user.age", value=65)
        cond2_diff_value = LessThanOrEqualCondition(key="user.age", value=64)
        cond3_diff_key = LessThanOrEqualCondition(key="item.stock", value=65)

        assert cond1a == cond1b
        assert cond1a != cond2_diff_value
        assert cond1a != cond3_diff_key
        assert cond1a != "some_other_type"

    def test_hash(self) -> None:
        cond1a = LessThanOrEqualCondition(key="user.age", value=65)
        cond1b = LessThanOrEqualCondition(key="user.age", value=65)
        cond2_diff_value = LessThanOrEqualCondition(key="user.age", value=64)

        assert hash(cond1a) == hash(cond1b)
        s = {cond1a, cond1b, cond2_diff_value}
        assert len(s) == 2
        assert cond1a in s
        assert cond2_diff_value in s


class TestGreaterThanConditionDunders:
    """Tests for __repr__, __eq__, and __hash__ on GreaterThanCondition."""

    def test_repr(self) -> None:
        cond = GreaterThanCondition(key="product.price", value=99.99)
        expected_repr = "GreaterThanCondition(key='product.price', value=99.99)"
        assert repr(cond) == expected_repr

    def test_eq(self) -> None:
        cond1a = GreaterThanCondition(key="product.price", value=99.99)
        cond1b = GreaterThanCondition(key="product.price", value=99.99)
        cond2_diff_value = GreaterThanCondition(key="product.price", value=50.00)
        cond3_diff_key = GreaterThanCondition(key="order.total", value=99.99)

        assert cond1a == cond1b
        assert cond1a != cond2_diff_value
        assert cond1a != cond3_diff_key
        assert cond1a != "some_other_type"

    def test_hash(self) -> None:
        cond1a = GreaterThanCondition(key="product.price", value=99.99)
        cond1b = GreaterThanCondition(key="product.price", value=99.99)
        cond2_diff_value = GreaterThanCondition(key="product.price", value=50.00)

        assert hash(cond1a) == hash(cond1b)
        s = {cond1a, cond1b, cond2_diff_value}
        assert len(s) == 2
        assert cond1a in s
        assert cond2_diff_value in s


class TestGreaterThanOrEqualConditionDunders:
    """Tests for __repr__, __eq__, and __hash__ on GreaterThanOrEqualCondition."""

    def test_repr(self) -> None:
        cond = GreaterThanOrEqualCondition(key="attempts", value=3)
        expected_repr = "GreaterThanOrEqualCondition(key='attempts', value=3)"
        assert repr(cond) == expected_repr

    def test_eq(self) -> None:
        cond1a = GreaterThanOrEqualCondition(key="attempts", value=3)
        cond1b = GreaterThanOrEqualCondition(key="attempts", value=3)
        cond2_diff_value = GreaterThanOrEqualCondition(key="attempts", value=4)
        cond3_diff_key = GreaterThanOrEqualCondition(key="max_retries", value=3)

        assert cond1a == cond1b
        assert cond1a != cond2_diff_value
        assert cond1a != cond3_diff_key
        assert cond1a != "some_other_type"

    def test_hash(self) -> None:
        cond1a = GreaterThanOrEqualCondition(key="attempts", value=3)
        cond1b = GreaterThanOrEqualCondition(key="attempts", value=3)
        cond2_diff_value = GreaterThanOrEqualCondition(key="attempts", value=4)

        assert hash(cond1a) == hash(cond1b)
        s = {cond1a, cond1b, cond2_diff_value}
        assert len(s) == 2
        assert cond1a in s
        assert cond2_diff_value in s


class TestRegexMatchConditionDunders:
    """Tests for __repr__, __eq__, and __hash__ on RegexMatchCondition."""

    def test_repr(self) -> None:
        cond = RegexMatchCondition(key="request.path", value="^/api/v[1-2]/")
        expected_repr = "RegexMatchCondition(key='request.path', value='^/api/v[1-2]/')"
        assert repr(cond) == expected_repr

    def test_eq(self) -> None:
        cond1a = RegexMatchCondition(key="request.path", value="^/api/v[1-2]/")
        cond1b = RegexMatchCondition(key="request.path", value="^/api/v[1-2]/")
        cond2_diff_value = RegexMatchCondition(key="request.path", value="^/public/")
        cond3_diff_key = RegexMatchCondition(key="user.email_domain", value=r"example\.com$")

        assert cond1a == cond1b
        assert cond1a != cond2_diff_value
        assert cond1a != cond3_diff_key
        assert cond1a != "some_other_type"

    def test_hash(self) -> None:
        cond1a = RegexMatchCondition(key="request.path", value="^/api/v[1-2]/")
        cond1b = RegexMatchCondition(key="request.path", value="^/api/v[1-2]/")
        cond2_diff_value = RegexMatchCondition(key="request.path", value="^/public/")

        assert hash(cond1a) == hash(cond1b)
        s = {cond1a, cond1b, cond2_diff_value}
        assert len(s) == 2
        assert cond1a in s
        assert cond2_diff_value in s


# --- Logical Conditions ---


class TestNotConditionDunders:
    """Tests for __repr__, __eq__, and __hash__ on NotCondition."""

    def test_repr(self) -> None:
        """Tests the __repr__ method of NotCondition."""
        inner_cond = EqualsCondition(key="data.isAdmin", value=True)
        not_cond = NotCondition(value=inner_cond)

        # The new __repr__ for NotCondition is f"{type(self).__name__}(value={self.cond!r})"
        # and for EqualsCondition it's f"{type(self).__name__}(key={self.key!r}, value={self.value!r})"
        # So, the expected repr will be a nested structure.
        expected_repr = f"NotCondition(value={inner_cond!r})"  # Relies on inner_cond's __repr__
        assert repr(not_cond) == expected_repr, "Repr string did not match"

    def test_eq(self) -> None:
        """Tests the __eq__ method of NotCondition."""
        inner_cond1 = EqualsCondition(key="data.isAdmin", value=True)
        inner_cond2 = EqualsCondition(key="data.isAdmin", value=False)  # Different inner value
        inner_cond3 = EqualsCondition(key="data.isUser", value=True)  # Different inner key

        cond1a = NotCondition(value=inner_cond1)
        cond1b = NotCondition(value=inner_cond1)  # Identical
        cond2_diff_inner_val = NotCondition(value=inner_cond2)  # Different inner condition (value)
        cond3_diff_inner_key = NotCondition(value=inner_cond3)  # Different inner condition (key)

        assert cond1a == cond1b, "Identical instances should be equal"
        assert cond1a != cond2_diff_inner_val, "Instances with different inner conditions (value) should not be equal"
        assert cond1a != cond3_diff_inner_key, "Instances with different inner conditions (key) should not be equal"
        assert cond1a != inner_cond1, "Instance should not be equal to its inner condition (diff type)"
        assert cond1a != "some_other_type", "Instance should not be equal to a string"

        # Test against a different logical condition type
        # For this, we need an AllCondition wrapping inner_cond1
        # This will fail due to isinstance check in Condition.__eq__
        other_logical_cond = AllCondition(conditions=[inner_cond1])
        assert cond1a != other_logical_cond, "NotCondition should not be equal to AllCondition"

    def test_hash(self) -> None:
        """Tests the __hash__ method of NotCondition."""
        inner_cond1 = EqualsCondition(key="data.isAdmin", value=True)
        inner_cond2 = EqualsCondition(key="data.isAdmin", value=False)

        cond1a = NotCondition(value=inner_cond1)
        cond1b = NotCondition(value=inner_cond1)
        cond2_diff_inner = NotCondition(value=inner_cond2)

        assert hash(cond1a) == hash(cond1b), "Hashes of identical instances should be equal"

        s = {cond1a, cond1b, cond2_diff_inner}
        assert len(s) == 2, "Set should contain 2 unique elements"
        assert cond1a in s
        assert cond2_diff_inner in s


class TestAllConditionDunders:
    """Tests for __repr__, __eq__, and __hash__ on AllCondition."""

    # Helper to create standard inner conditions for tests
    @pytest.fixture
    def inner_conds_set1(self) -> list[Condition]:
        return [EqualsCondition(key="req.method", value="POST"), ContainsCondition(key="req.path", value="/submit")]

    @pytest.fixture
    def inner_conds_set2(
        self,
    ) -> list[Condition]:  # Different order, should still be equal if list comparison is order-sensitive
        return [ContainsCondition(key="req.path", value="/submit"), EqualsCondition(key="req.method", value="POST")]

    @pytest.fixture
    def inner_conds_set3(self) -> list[Condition]:  # Different content
        return [
            EqualsCondition(key="req.method", value="GET"),  # Different value
            ContainsCondition(key="req.path", value="/submit"),
        ]

    @pytest.fixture
    def inner_conds_set4(self) -> list[Condition]:  # Different number of conditions
        return [EqualsCondition(key="req.method", value="POST")]

    def test_repr(self, inner_conds_set1: list[Condition]) -> None:
        """Tests the __repr__ method of AllCondition."""
        all_cond = AllCondition(conditions=inner_conds_set1)

        # The new __repr__ for AllCondition is f"{type(self).__name__}(conditions={self.conditions!r})"
        # This will use the __repr__ of the list, which in turn uses the __repr__ of its elements.
        expected_repr = f"AllCondition(conditions={inner_conds_set1!r})"
        assert repr(all_cond) == expected_repr

    def test_eq(
        self,
        inner_conds_set1: list[Condition],
        inner_conds_set2: list[Condition],
        inner_conds_set3: list[Condition],
        inner_conds_set4: list[Condition],
    ) -> None:
        """Tests the __eq__ method of AllCondition."""
        cond1a = AllCondition(conditions=inner_conds_set1)
        cond1b = AllCondition(conditions=list(inner_conds_set1))  # Identical content, new list instance

        # Since Condition.__eq__ relies on serialize(), and serialize() for AllCondition
        # serializes the list of conditions in order, the order of conditions matters for equality.
        cond1c_diff_order = AllCondition(conditions=inner_conds_set2)  # Same conditions, different order

        cond2_diff_content = AllCondition(conditions=inner_conds_set3)  # Different inner condition
        cond3_diff_count = AllCondition(conditions=inner_conds_set4)  # Different number of inner conditions

        assert cond1a == cond1b, "Instances with identical condition lists should be equal"

        # The current implementation of Condition.__eq__ relies on serialize(), which for AllCondition
        # serializes the list of conditions. Standard list comparison is order-sensitive.
        # Thus, if inner_conds_set1 and inner_conds_set2 have the same elements but different order,
        # their serialized forms will be different, and thus cond1a != cond1c_diff_order.
        # This is the expected behavior given the current Condition base class implementation.
        if inner_conds_set1 == inner_conds_set2:  # If lists happen to be identical despite fixture setup
            assert cond1a == cond1c_diff_order, "Instances with same-ordered identical conditions should be equal"
        else:  # If lists are truly different order
            assert cond1a != cond1c_diff_order, (
                "Instances with differently ordered conditions should NOT be equal (due to list serialization order)"
            )

        assert cond1a != cond2_diff_content, "Instances with different inner conditions should not be equal"
        assert cond1a != cond3_diff_count, "Instances with different number of inner conditions should not be equal"
        assert cond1a != "some_other_type", "Instance should not be equal to a string"

        # Test against a different logical condition type
        other_logical_cond = AnyCondition(conditions=inner_conds_set1)
        assert cond1a != other_logical_cond, "AllCondition should not be equal to AnyCondition"

    def test_hash(
        self, inner_conds_set1: list[Condition], inner_conds_set2: list[Condition], inner_conds_set3: list[Condition]
    ) -> None:
        """Tests the __hash__ method of AllCondition."""
        cond1a = AllCondition(conditions=inner_conds_set1)
        cond1b = AllCondition(conditions=list(inner_conds_set1))  # Identical

        # See note in test_eq about order for cond1c_diff_order
        cond1c_diff_order = AllCondition(conditions=inner_conds_set2)

        cond2_diff_content = AllCondition(conditions=inner_conds_set3)

        assert hash(cond1a) == hash(cond1b), "Hashes of identical instances should be equal"

        s = {cond1a, cond1b, cond2_diff_content}
        if cond1a == cond1c_diff_order:  # if order didn't matter or lists were same
            s.add(cond1c_diff_order)
            assert len(s) == 2, "Set should contain 2 unique elements if order doesn't affect equality"
        else:  # if order matters and lists are different
            s.add(cond1c_diff_order)
            assert len(s) == 3, "Set should contain 3 unique elements if order affects equality"
            assert cond1c_diff_order in s, "cond1c_diff_order should be in the set if distinct"

        assert cond1a in s
        assert cond2_diff_content in s


class TestAnyConditionDunders:
    """Tests for __repr__, __eq__, and __hash__ on AnyCondition."""

    # Reuse fixtures from AllCondition tests for brevity if applicable, or define new ones.
    @pytest.fixture
    def inner_conds_set1(self) -> list[Condition]:
        return [EqualsCondition(key="user.role", value="admin"), GreaterThanCondition(key="user.level", value=5)]

    @pytest.fixture
    def inner_conds_set2(self) -> list[Condition]:  # Different order
        return [GreaterThanCondition(key="user.level", value=5), EqualsCondition(key="user.role", value="admin")]

    @pytest.fixture
    def inner_conds_set3(self) -> list[Condition]:  # Different content
        return [
            EqualsCondition(key="user.role", value="editor"),  # Diff value
            GreaterThanCondition(key="user.level", value=5),
        ]

    def test_repr(self, inner_conds_set1: list[Condition]) -> None:
        """Tests the __repr__ method of AnyCondition."""
        any_cond = AnyCondition(conditions=inner_conds_set1)

        # Similar to AllCondition, uses the list's repr.
        expected_repr = f"AnyCondition(conditions={inner_conds_set1!r})"
        assert repr(any_cond) == expected_repr

    def test_eq(
        self, inner_conds_set1: list[Condition], inner_conds_set2: list[Condition], inner_conds_set3: list[Condition]
    ) -> None:
        """Tests the __eq__ method of AnyCondition."""
        cond1a = AnyCondition(conditions=inner_conds_set1)
        cond1b = AnyCondition(conditions=list(inner_conds_set1))
        cond1c_diff_order = AnyCondition(conditions=inner_conds_set2)  # Same elements, different order
        cond2_diff_content = AnyCondition(conditions=inner_conds_set3)

        assert cond1a == cond1b

        # As with AllCondition, equality is order-sensitive due to list serialization
        if inner_conds_set1 == inner_conds_set2:
            assert cond1a == cond1c_diff_order
        else:
            assert cond1a != cond1c_diff_order

        assert cond1a != cond2_diff_content
        assert cond1a != "some_other_type"
        other_logical_cond = AllCondition(conditions=inner_conds_set1)
        assert cond1a != other_logical_cond

    def test_hash(
        self, inner_conds_set1: list[Condition], inner_conds_set2: list[Condition], inner_conds_set3: list[Condition]
    ) -> None:
        """Tests the __hash__ method of AnyCondition."""
        cond1a = AnyCondition(conditions=inner_conds_set1)
        cond1b = AnyCondition(conditions=list(inner_conds_set1))
        cond1c_diff_order = AnyCondition(conditions=inner_conds_set2)
        cond2_diff_content = AnyCondition(conditions=inner_conds_set3)

        assert hash(cond1a) == hash(cond1b)

        s = {cond1a, cond1b, cond2_diff_content}
        if cond1a == cond1c_diff_order:
            s.add(cond1c_diff_order)
            assert len(s) == 2
        else:
            s.add(cond1c_diff_order)
            assert len(s) == 3
            assert cond1c_diff_order in s

        assert cond1a in s
        assert cond2_diff_content in s
