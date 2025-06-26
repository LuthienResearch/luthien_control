from typing import Any

import pytest
from luthien_control.api.openai_chat_completions.datatypes import Choice, Message, Usage
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse
from luthien_control.control_policy.conditions.value_resolvers import (
    VALUE_RESOLVER_REGISTRY,
    StaticValue,
    TransactionPath,
    ValueResolver,
    auto_resolve_value,
    create_value_resolver,
    path,
)
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.request import Request
from luthien_control.core.response import Response
from luthien_control.core.transaction import Transaction
from psygnal.containers import EventedList


@pytest.fixture
def sample_transaction() -> Transaction:
    """Create a sample transaction for testing."""
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

    response = Response(
        payload=OpenAIChatCompletionsResponse(
            id="chatcmpl-test123",
            model="gpt-4o",
            created=1734567890,
            choices=EventedList(
                [
                    Choice(
                        index=0,
                        message=Message(role="assistant", content="Hello! How can I help you today?"),
                        finish_reason="stop",
                    )
                ]
            ),
            usage=Usage(prompt_tokens=10, completion_tokens=15, total_tokens=25),
        ),
    )

    return Transaction(request=request, response=response)


class TestCreateValueResolver:
    """Test the create_value_resolver function."""

    def test_create_static_value_resolver(self):
        """Test creating a StaticValue resolver from serialized data."""
        serialized: SerializableDict = {"type": "static", "value": "test_value"}
        resolver = create_value_resolver(serialized)

        assert isinstance(resolver, StaticValue)
        assert resolver.value == "test_value"

    def test_create_transaction_path_resolver(self):
        """Test creating a TransactionPath resolver from serialized data."""
        serialized: SerializableDict = {"type": "transaction_path", "path": "request.payload.model"}
        resolver = create_value_resolver(serialized)

        assert isinstance(resolver, TransactionPath)
        assert resolver.path == "request.payload.model"

    def test_create_value_resolver_unknown_type(self):
        """Test that create_value_resolver raises ValueError for unknown types."""
        serialized: SerializableDict = {"type": "unknown_type", "value": "test"}

        with pytest.raises(ValueError, match="Unknown value resolver type: unknown_type"):
            create_value_resolver(serialized)

    def test_create_value_resolver_missing_type(self):
        """Test that create_value_resolver raises ValueError when type is None."""
        serialized: SerializableDict = {"value": "test"}  # Missing type field

        with pytest.raises(ValueError, match="Unknown value resolver type: None"):
            create_value_resolver(serialized)

    def test_create_value_resolver_invalid_type_data(self):
        """Test that create_value_resolver propagates errors from resolver creation."""
        # TransactionPath requires a string path, not an integer
        serialized: SerializableDict = {"type": "transaction_path", "path": 123}

        with pytest.raises(TypeError, match="TransactionPath path must be a string"):
            create_value_resolver(serialized)


class TestAutoResolveValue:
    """Test the auto_resolve_value function."""

    def test_auto_resolve_value_with_resolver(self, sample_transaction: Transaction):
        """Test that auto_resolve_value returns ValueResolver instances unchanged."""
        resolver = StaticValue("test")
        result = auto_resolve_value(resolver)

        assert result is resolver

    def test_auto_resolve_value_with_static_value(self, sample_transaction: Transaction):
        """Test that auto_resolve_value wraps non-ValueResolver values in StaticValue."""
        value = "test_string"
        result = auto_resolve_value(value)

        assert isinstance(result, StaticValue)
        assert result.value == value
        assert result.resolve(sample_transaction) == value

    def test_auto_resolve_value_with_none(self, sample_transaction: Transaction):
        """Test that auto_resolve_value handles None values."""
        result = auto_resolve_value(None)

        assert isinstance(result, StaticValue)
        assert result.value is None
        assert result.resolve(sample_transaction) is None


class TestPathConvenienceFunction:
    """Test the path convenience function."""

    def test_path_function(self, sample_transaction: Transaction):
        """Test that path() creates a TransactionPath with the correct path."""
        resolver = path("request.payload.model")

        assert isinstance(resolver, TransactionPath)
        assert resolver.path == "request.payload.model"
        assert resolver.resolve(sample_transaction) == "gpt-4o"


class TestValueResolverRegistry:
    """Test the VALUE_RESOLVER_REGISTRY."""

    def test_registry_contains_expected_types(self):
        """Test that the registry contains the expected resolver types."""
        assert "static" in VALUE_RESOLVER_REGISTRY
        assert "transaction_path" in VALUE_RESOLVER_REGISTRY
        assert VALUE_RESOLVER_REGISTRY["static"] is StaticValue
        assert VALUE_RESOLVER_REGISTRY["transaction_path"] is TransactionPath

    def test_registry_is_extensible(self):
        """Test that the registry can be extended (for future development)."""
        # This test documents the current behavior and ensures the registry
        # is a regular dict that can be modified if needed in the future
        original_size = len(VALUE_RESOLVER_REGISTRY)

        # Temporarily add a test resolver
        class TestResolver(ValueResolver):
            def resolve(self, transaction: Transaction) -> Any:
                return "test"

            def serialize(self) -> SerializableDict:
                return {"type": "test"}

            @classmethod
            def from_serialized(cls, serialized: SerializableDict) -> "TestResolver":
                return cls()

        VALUE_RESOLVER_REGISTRY["test"] = TestResolver

        try:
            assert len(VALUE_RESOLVER_REGISTRY) == original_size + 1
            assert VALUE_RESOLVER_REGISTRY["test"] is TestResolver

            # Test that create_value_resolver works with the new type
            resolver = create_value_resolver({"type": "test"})
            assert isinstance(resolver, TestResolver)
        finally:
            # Clean up
            del VALUE_RESOLVER_REGISTRY["test"]

        assert len(VALUE_RESOLVER_REGISTRY) == original_size
