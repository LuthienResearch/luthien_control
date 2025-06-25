from typing import Any, cast

import pytest
from luthien_control.api.openai_chat_completions.datatypes import (
    Choice,
    Message,
    Usage,
)
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse
from luthien_control.control_policy.conditions.comparison_conditions import (
    ContainsCondition,
    EqualsCondition,
    GreaterThanCondition,
    LessThanCondition,
    NotEqualsCondition,
    RegexMatchCondition,
)
from luthien_control.control_policy.conditions.value_resolvers import (
    StaticValue,
    TransactionPath,
    path,
)
from luthien_control.core.request import Request
from luthien_control.core.response import Response
from luthien_control.core.transaction import Transaction
from psygnal.containers import EventedDict, EventedList


@pytest.fixture
def sample_transaction_clean() -> Transaction:
    """Provides a Transaction with data for testing clean comparisons."""

    # Create request with OpenAI chat completions data
    request = Request(
        payload=OpenAIChatCompletionsRequest(
            model="gpt-4o",
            messages=EventedList([Message(role="user", content="Hello")]),
            max_tokens=500,
            temperature=0.7,
        ),
        api_endpoint="https://api.openai.com/v1/chat/completions",
        api_key="Bearer testkey",
    )

    # Create response
    response = Response(
        payload=OpenAIChatCompletionsResponse(
            id="chatcmpl-test123",
            model="gpt-4o",
            created=1734567890,
            choices=EventedList([Choice(message=Message(role="assistant", content="Hi there!"))]),
            usage=Usage(prompt_tokens=50, completion_tokens=100, total_tokens=150),
        ),
    )

    # Create transaction with additional data
    transaction = Transaction(request=request, response=response)
    transaction.data = EventedDict(
        {
            "preferred_model": "gpt-4o",
            "alternative_model": "gpt-3.5-turbo",
            "static_value": "test_static",
            "settings": EventedDict(
                {
                    "max_tokens_limit": 1000,
                    "min_tokens_limit": 100,
                    "default_temperature": 0.7,
                    "allowed_models": EventedList(["gpt-4o", "gpt-3.5-turbo", "claude-3"]),
                }
            ),
            "user_limits": EventedDict(
                {
                    "max_tokens": 500,
                    "daily_requests": 1000,
                }
            ),
            "patterns": EventedDict(
                {
                    "model_pattern": "gpt-4.*",
                    "endpoint_pattern": ".*openai.*",
                }
            ),
        }
    )

    return transaction


class TestValueResolvers:
    def test_static_value_resolver(self, sample_transaction_clean: Transaction):
        """Test StaticValue resolver."""
        resolver = StaticValue("test_value")
        assert resolver.resolve(sample_transaction_clean) == "test_value"

    def test_transaction_path_resolver(self, sample_transaction_clean: Transaction):
        """Test TransactionPath resolver."""
        resolver = TransactionPath("request.payload.model")
        assert resolver.resolve(sample_transaction_clean) == "gpt-4o"

    def test_path_convenience_function(self, sample_transaction_clean: Transaction):
        """Test the path() convenience function."""
        resolver = path("request.payload.model")
        assert isinstance(resolver, TransactionPath)
        assert resolver.resolve(sample_transaction_clean) == "gpt-4o"

    def test_transaction_path_invalid_path(self, sample_transaction_clean: Transaction):
        """Test TransactionPath with invalid path returns None."""
        resolver = TransactionPath("request.nonexistent.path")
        assert resolver.resolve(sample_transaction_clean) is None

    def test_static_value_serialization(self):
        """Test StaticValue serialization."""
        resolver = StaticValue("test_value")
        serialized = resolver.serialize()
        assert serialized == {"type": "static", "value": "test_value"}

        deserialized = StaticValue.from_serialized(serialized)
        assert deserialized.value == "test_value"

    def test_transaction_path_serialization(self):
        """Test TransactionPath serialization."""
        resolver = TransactionPath("request.payload.model")
        serialized = resolver.serialize()
        assert serialized == {"type": "transaction_path", "path": "request.payload.model"}

        deserialized = TransactionPath.from_serialized(serialized)
        assert deserialized.path == "request.payload.model"

    def test_static_value_equality(self):
        """Test StaticValue equality."""
        resolver1 = StaticValue("test")
        resolver2 = StaticValue("test")
        resolver3 = StaticValue("different")

        assert resolver1 == resolver2
        assert resolver1 != resolver3
        assert resolver1 != "not_a_resolver"

    def test_transaction_path_equality(self):
        """Test TransactionPath equality."""
        resolver1 = TransactionPath("request.payload.model")
        resolver2 = TransactionPath("request.payload.model")
        resolver3 = TransactionPath("data.model")

        assert resolver1 == resolver2
        assert resolver1 != resolver3
        assert resolver1 != "not_a_resolver"


class TestCleanEqualsCondition:
    def test_traditional_path_vs_static(self, sample_transaction_clean: Transaction):
        """Test traditional format: transaction path vs static value."""
        condition = EqualsCondition(path("request.payload.model"), "gpt-4o")
        assert condition.evaluate(sample_transaction_clean) is True

    def test_auto_resolution_path_vs_static(self, sample_transaction_clean: Transaction):
        """Test auto-resolution of static values."""
        condition = EqualsCondition(path("request.payload.model"), "gpt-4o")
        assert condition.evaluate(sample_transaction_clean) is True

    def test_path_vs_path(self, sample_transaction_clean: Transaction):
        """Test dynamic comparison: transaction path vs transaction path."""
        condition = EqualsCondition(path("request.payload.model"), path("data.preferred_model"))
        assert condition.evaluate(sample_transaction_clean) is True

    def test_static_vs_path(self, sample_transaction_clean: Transaction):
        """Test static value vs transaction path."""
        condition = EqualsCondition("gpt-4o", path("request.payload.model"))
        assert condition.evaluate(sample_transaction_clean) is True

    def test_static_vs_static(self, sample_transaction_clean: Transaction):
        """Test static value vs static value."""
        condition = EqualsCondition("test_value", "test_value")
        assert condition.evaluate(sample_transaction_clean) is True

    def test_static_vs_static_false(self, sample_transaction_clean: Transaction):
        """Test static value vs static value that don't match."""
        condition = EqualsCondition("test_value", "different_value")
        assert condition.evaluate(sample_transaction_clean) is False

    def test_numeric_comparison(self, sample_transaction_clean: Transaction):
        """Test comparing numeric values dynamically."""
        condition = EqualsCondition(path("request.payload.temperature"), path("data.settings.default_temperature"))
        assert condition.evaluate(sample_transaction_clean) is True

    def test_serialization_path_vs_static(self):
        """Test serialization of path vs static value."""
        condition = EqualsCondition(path("request.payload.model"), "gpt-4o")
        serialized = condition.serialize()

        expected = {
            "type": "equals",
            "left": {"type": "transaction_path", "path": "request.payload.model"},
            "right": {"type": "static", "value": "gpt-4o"},
            "comparator": "equals",
        }
        assert serialized == expected

    def test_serialization_path_vs_path(self):
        """Test serialization of path vs path."""
        condition = EqualsCondition(path("request.payload.model"), path("data.preferred_model"))
        serialized = condition.serialize()

        expected = {
            "type": "equals",
            "left": {"type": "transaction_path", "path": "request.payload.model"},
            "right": {"type": "transaction_path", "path": "data.preferred_model"},
            "comparator": "equals",
        }
        assert serialized == expected

    def test_serialization_static_vs_static(self):
        """Test serialization of static vs static."""
        condition = EqualsCondition("value1", "value2")
        serialized = condition.serialize()

        expected = {
            "type": "equals",
            "left": {"type": "static", "value": "value1"},
            "right": {"type": "static", "value": "value2"},
            "comparator": "equals",
        }
        assert serialized == expected

    def test_deserialization_path_vs_static(self, sample_transaction_clean: Transaction):
        """Test deserialization of path vs static."""
        serialized = {
            "type": "equals",
            "left": {"type": "transaction_path", "path": "request.payload.model"},
            "right": {"type": "static", "value": "gpt-4o"},
            "comparator": "equals",
        }
        condition = EqualsCondition.from_serialized(cast(Any, serialized))

        assert isinstance(condition.left_resolver, TransactionPath)
        assert condition.left_resolver.path == "request.payload.model"
        assert isinstance(condition.right_resolver, StaticValue)
        assert condition.right_resolver.value == "gpt-4o"
        assert condition.evaluate(sample_transaction_clean) is True

    def test_deserialization_path_vs_path(self, sample_transaction_clean: Transaction):
        """Test deserialization of path vs path."""
        serialized = {
            "type": "equals",
            "left": {"type": "transaction_path", "path": "request.payload.model"},
            "right": {"type": "transaction_path", "path": "data.preferred_model"},
            "comparator": "equals",
        }
        condition = EqualsCondition.from_serialized(cast(Any, serialized))

        assert isinstance(condition.left_resolver, TransactionPath)
        assert condition.left_resolver.path == "request.payload.model"
        assert isinstance(condition.right_resolver, TransactionPath)
        assert condition.right_resolver.path == "data.preferred_model"
        assert condition.evaluate(sample_transaction_clean) is True

    def test_legacy_format_compatibility(self, sample_transaction_clean: Transaction):
        """Test compatibility with legacy format."""
        condition = EqualsCondition.from_legacy_format(key="request.payload.model", value="gpt-4o")

        assert isinstance(condition.left_resolver, TransactionPath)
        assert condition.left_resolver.path == "request.payload.model"
        assert isinstance(condition.right_resolver, StaticValue)
        assert condition.right_resolver.value == "gpt-4o"
        assert condition.evaluate(sample_transaction_clean) is True


class TestOtherCleanConditions:
    def test_not_equals_condition(self, sample_transaction_clean: Transaction):
        """Test NotEqualsCondition."""
        condition = NotEqualsCondition(path("request.payload.model"), path("data.alternative_model"))
        assert condition.evaluate(sample_transaction_clean) is True

    def test_contains_condition_static(self, sample_transaction_clean: Transaction):
        """Test ContainsCondition with static contains."""
        condition = ContainsCondition(path("data.settings.allowed_models"), "gpt-4o")
        assert condition.evaluate(sample_transaction_clean) is True

    def test_contains_condition_dynamic(self, sample_transaction_clean: Transaction):
        """Test ContainsCondition with dynamic contains."""
        condition = ContainsCondition(path("data.settings.allowed_models"), path("request.payload.model"))
        assert condition.evaluate(sample_transaction_clean) is True

    def test_contains_condition_static_left(self, sample_transaction_clean: Transaction):
        """Test ContainsCondition with static left value."""
        condition = ContainsCondition(["gpt-4o", "gpt-3.5-turbo"], path("request.payload.model"))
        assert condition.evaluate(sample_transaction_clean) is True

    def test_less_than_condition_static(self, sample_transaction_clean: Transaction):
        """Test LessThanCondition with static value."""
        condition = LessThanCondition(path("request.payload.max_tokens"), 1000)
        assert condition.evaluate(sample_transaction_clean) is True

    def test_less_than_condition_dynamic(self, sample_transaction_clean: Transaction):
        """Test LessThanCondition with dynamic comparison."""
        condition = LessThanCondition(path("request.payload.max_tokens"), path("data.settings.max_tokens_limit"))
        assert condition.evaluate(sample_transaction_clean) is True

    def test_less_than_condition_static_left(self, sample_transaction_clean: Transaction):
        """Test LessThanCondition with static left value."""
        condition = LessThanCondition(50, path("response.payload.usage.total_tokens"))
        assert condition.evaluate(sample_transaction_clean) is True

    def test_greater_than_condition(self, sample_transaction_clean: Transaction):
        """Test GreaterThanCondition."""
        condition = GreaterThanCondition(
            path("response.payload.usage.total_tokens"), path("response.payload.usage.prompt_tokens")
        )
        assert condition.evaluate(sample_transaction_clean) is True

    def test_regex_match_condition_static(self, sample_transaction_clean: Transaction):
        """Test RegexMatchCondition with static pattern."""
        condition = RegexMatchCondition(path("request.payload.model"), "gpt-4.*")
        assert condition.evaluate(sample_transaction_clean) is True

    def test_regex_match_condition_dynamic(self, sample_transaction_clean: Transaction):
        """Test RegexMatchCondition with dynamic pattern."""
        condition = RegexMatchCondition(path("request.payload.model"), path("data.patterns.model_pattern"))
        assert condition.evaluate(sample_transaction_clean) is True

    def test_regex_match_condition_static_left(self, sample_transaction_clean: Transaction):
        """Test RegexMatchCondition with static left value."""
        condition = RegexMatchCondition("gpt-4o", path("data.patterns.model_pattern"))
        assert condition.evaluate(sample_transaction_clean) is True


class TestErrorHandling:
    def test_invalid_left_path(self, sample_transaction_clean: Transaction):
        """Test handling of invalid left path."""
        condition = EqualsCondition(path("request.nonexistent.path"), "gpt-4o")
        # Should return False when comparing None to "gpt-4o"
        assert condition.evaluate(sample_transaction_clean) is False

    def test_invalid_right_path(self, sample_transaction_clean: Transaction):
        """Test handling of invalid right path."""
        condition = EqualsCondition(path("request.payload.model"), path("data.nonexistent.path"))
        # Should return False when comparing "gpt-4o" to None
        assert condition.evaluate(sample_transaction_clean) is False

    def test_invalid_both_paths(self, sample_transaction_clean: Transaction):
        """Test handling when both paths are invalid."""
        condition = EqualsCondition(path("request.nonexistent.path1"), path("data.nonexistent.path2"))
        # Should return True when comparing None to None
        assert condition.evaluate(sample_transaction_clean) is True

    def test_deserialization_invalid_left_type(self):
        """Test deserialization with invalid left type."""
        serialized = {
            "type": "equals",
            "left": "not_a_dict",  # Should be a dict
            "right": {"type": "static", "value": "gpt-4o"},
            "comparator": "equals",
        }
        with pytest.raises(TypeError, match="Left and right must be serialized ValueResolver objects"):
            EqualsCondition.from_serialized(cast(Any, serialized))

    def test_deserialization_invalid_right_type(self):
        """Test deserialization with invalid right type."""
        serialized = {
            "type": "equals",
            "left": {"type": "transaction_path", "path": "request.payload.model"},
            "right": "not_a_dict",  # Should be a dict
            "comparator": "equals",
        }
        with pytest.raises(TypeError, match="Left and right must be serialized ValueResolver objects"):
            EqualsCondition.from_serialized(cast(Any, serialized))

    def test_transaction_path_invalid_serialization(self):
        """Test TransactionPath deserialization with invalid path type."""
        serialized = {"type": "transaction_path", "path": 123}  # Should be string
        with pytest.raises(TypeError, match="TransactionPath path must be a string"):
            TransactionPath.from_serialized(serialized)

    def test_repr(self):
        """Test string representation."""
        condition = EqualsCondition(path("request.payload.model"), "gpt-4o")
        repr_str = repr(condition)
        assert "EqualsCondition" in repr_str
        assert "TransactionPath" in repr_str
        assert "StaticValue" in repr_str
