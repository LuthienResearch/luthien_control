import builtins
import logging
from unittest.mock import MagicMock

import pytest
from luthien_control.api.openai_chat_completions.datatypes import Choice, Message, Usage
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse
from luthien_control.control_policy.transaction_context_logging_policy import (
    TransactionContextLoggingPolicy,
)
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.raw_request import RawRequest
from luthien_control.core.raw_response import RawResponse
from luthien_control.core.request import Request
from luthien_control.core.response import Response
from luthien_control.core.streaming_response import ChunkedTextIterator
from luthien_control.core.transaction import Transaction
from psygnal.containers import EventedList
from sqlalchemy.ext.asyncio import AsyncSession

# Test Data Constants
SENSITIVE_FIELDS_DATA = [
    # (field_name, value, expected)
    ("api_key", "sk-1234567890abcdefghijklmnop", "sk-1***"),
    ("authorization", "Bearer sk-1234567890abcdef", "Bearer ***"),
    ("password", "secret123", "secr***"),
    ("token", "very_long_token_value", "very***"),
    ("api-key", "short", "***"),
    ("pwd", "a", "***"),  # Very short string
]

NON_SENSITIVE_DATA = [
    ("user_id", "12345"),
    ("model", "gpt-4"),
    ("count", 42),
    ("enabled", True),
    ("api_key", ""),  # Empty string case
    ("api_key", None),  # None case
]

INITIALIZATION_PARAMS = [
    (None, None, "TransactionContextLoggingPolicy", "INFO"),
    ("CustomPolicy", "DEBUG", "CustomPolicy", "DEBUG"),
    (None, "WARNING", "TransactionContextLoggingPolicy", "WARNING"),
]

LOG_LEVELS = [
    ("INFO", logging.INFO),
    ("DEBUG", logging.DEBUG),
    ("WARNING", logging.WARNING),
]


@pytest.fixture
def sample_transaction() -> Transaction:
    """Provides a Transaction for testing."""
    request = Request(
        payload=OpenAIChatCompletionsRequest(
            model="gpt-4",
            messages=EventedList([Message(role="user", content="Hello, world!")]),
        ),
        api_endpoint="https://api.openai.com/v1/chat/completions",
        api_key="sk-test123456789",
    )

    response = Response(
        payload=OpenAIChatCompletionsResponse(
            id="test_id",
            object="chat.completion",
            created=1234567890,
            model="gpt-4",
            choices=EventedList(
                [
                    Choice(
                        index=0,
                        message=Message(role="assistant", content="Hello back!"),
                        finish_reason="stop",
                    )
                ]
            ),
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        ),
        api_endpoint="https://api.openai.com/v1/chat/completions",
    )

    return Transaction(openai_request=request, openai_response=response)


@pytest.fixture
def mock_dependencies():
    """Provides mock dependencies for testing."""
    return MagicMock(spec=DependencyContainer), MagicMock(spec=AsyncSession)


@pytest.fixture
def policy():
    """Provides a policy instance for testing."""
    return TransactionContextLoggingPolicy()


class TestTransactionContextLoggingPolicy:
    """Test cases for TransactionContextLoggingPolicy."""

    @pytest.mark.parametrize("name,log_level,expected_name,expected_level", INITIALIZATION_PARAMS)
    def test_initialization(self, name, log_level, expected_name, expected_level):
        """Test policy initialization with various parameters."""
        kwargs = {}
        if name is not None:
            kwargs["name"] = name
        if log_level is not None:
            kwargs["log_level"] = log_level

        policy = TransactionContextLoggingPolicy(**kwargs)
        assert policy.name == expected_name
        assert policy.log_level == expected_level
        assert policy.type == "TransactionContextLoggingPolicy"

    @pytest.mark.parametrize("field_name,value,expected", SENSITIVE_FIELDS_DATA)
    def test_sensitive_data_redaction(self, policy, field_name, value, expected):
        """Test that sensitive data fields are properly redacted."""
        result = policy._redact_value(field_name, value)
        assert result == expected

    @pytest.mark.parametrize("field_name,value", NON_SENSITIVE_DATA)
    def test_non_sensitive_data_preserved(self, policy, field_name, value):
        """Test that non-sensitive data is preserved."""
        result = policy._redact_value(field_name, value)
        if field_name in ["api_key", "password"] and isinstance(value, str) and value and len(value) <= 2:
            assert result == "***"
        else:
            assert result == value

    def test_nested_structure_redaction(self, policy):
        """Test that nested data structures are properly redacted."""
        data = {
            "user_info": {"name": "John", "api_key": "sk-1234567890abcdef"},
            "headers": [{"name": "Authorization", "value": "Bearer secret_token"}],
            "config": {"database": {"password": "db_secret_password"}},
        }

        result = policy._redact_sensitive_data(data)

        assert result["user_info"]["name"] == "John"
        assert result["user_info"]["api_key"] == "sk-1***"
        assert result["headers"][0]["value"] == "Bearer ***"
        assert result["config"]["database"]["password"] == "db_s***"

    def test_transaction_serialization_core_fields(self, policy, sample_transaction):
        """Test serialization includes core transaction fields with redaction."""
        context = policy._serialize_transaction_context(sample_transaction)

        # Core fields present
        assert "transaction_id" in context
        assert "openai_request" in context

        # Sensitive data redacted
        assert context["openai_request"]["api_key"] == "sk-t***"

    def test_transaction_with_custom_data(self, policy, sample_transaction):
        """Test transaction data serialization with redaction."""
        sample_transaction.data.update(
            {"user_id": "12345", "secret_key": "very_secret_value", "api_key": "sk-abcdefghijklmnop"}
        )

        context = policy._serialize_transaction_context(sample_transaction)
        data = context["transaction_data"]

        assert data["user_id"] == "12345"  # Not redacted
        assert data["secret_key"] == "very***"  # Redacted
        assert data["api_key"] == "sk-a***"  # Redacted

    @pytest.mark.asyncio
    @pytest.mark.parametrize("log_level,expected_level", LOG_LEVELS)
    async def test_apply_logs_at_correct_level(
        self, sample_transaction, mock_dependencies, caplog, log_level, expected_level
    ):
        """Test that apply method logs at the specified level."""
        policy = TransactionContextLoggingPolicy(log_level=log_level)
        container, session = mock_dependencies

        with caplog.at_level(expected_level):
            result = await policy.apply(sample_transaction, container, session)

        assert result is sample_transaction
        assert len(caplog.records) == 1
        assert "Transaction Context JSON:" in caplog.records[0].message
        assert caplog.records[0].levelno == expected_level

    @pytest.mark.asyncio
    async def test_apply_handles_errors_gracefully(self, sample_transaction, mock_dependencies, caplog):
        """Test that apply method handles serialization errors gracefully."""
        policy = TransactionContextLoggingPolicy()
        container, session = mock_dependencies

        # Mock serialization to fail
        policy._serialize_transaction_context = lambda transaction: (_ for _ in ()).throw(ValueError("Failed"))

        with caplog.at_level(logging.ERROR):
            result = await policy.apply(sample_transaction, container, session)

        assert result is sample_transaction
        assert "Failed to log transaction context" in caplog.records[0].message

    def test_serialization_roundtrip(self):
        """Test policy serialization and deserialization."""
        original = TransactionContextLoggingPolicy(name="TestPolicy", log_level="WARNING")

        serialized = original.serialize()
        deserialized = TransactionContextLoggingPolicy.from_serialized(serialized)

        assert deserialized.name == original.name
        assert deserialized.log_level == original.log_level

    def test_api_key_pattern_recognition(self, policy):
        """Test recognition of API key patterns."""
        # OpenAI-style key redacted by pattern
        result = policy._redact_value("field", "sk-1234567890abcdefghijklmnopqrstuvwxyz")
        assert result == "sk-1***"

        # Generic key only redacted for sensitive field names
        generic_key = "abcdefghijklmnopqrstuvwxyz123456"
        assert policy._redact_value("field", generic_key) == generic_key
        assert policy._redact_value("api_key", generic_key) == "abcd***"

    def test_streaming_response_handling(self, policy):
        """Test that streaming responses are handled correctly."""
        request = Request(
            payload=OpenAIChatCompletionsRequest(
                model="gpt-4",
                messages=EventedList([Message(role="user", content="Hello!")]),
                stream=True,
            ),
            api_endpoint="https://api.openai.com/v1/chat/completions",
            api_key="sk-test123456789",
        )

        streaming_iterator = ChunkedTextIterator("Hello world", chunk_size=5)
        response = Response(streaming_iterator=streaming_iterator)
        transaction = Transaction(openai_request=request, openai_response=response)

        context = policy._serialize_transaction_context(transaction)

        assert context["openai_response"]["is_streaming"] is True
        assert context["openai_response"]["streaming_iterator"]["_is_streaming_iterator"] is True

    def test_raw_response_streaming(self, policy):
        """Test raw response with streaming iterator."""
        raw_request = RawRequest(
            method="GET",
            path="v1/models",
            headers={},
            body=b"",
            api_key="test-key",
            backend_url="https://api.example.com",
        )

        streaming_iterator = ChunkedTextIterator("raw data", chunk_size=8)
        raw_response = RawResponse(status_code=200, headers={}, streaming_iterator=streaming_iterator)

        transaction = Transaction(raw_request=raw_request, raw_response=raw_response)
        context = policy._serialize_transaction_context(transaction)

        assert context["raw_response"]["is_streaming"] is True
        assert context["raw_response"]["streaming_iterator"]["_is_streaming_iterator"] is True

    # Edge Case Tests - Combined for efficiency
    def test_edge_cases(self, policy):
        """Test various edge cases in a single comprehensive test."""
        # Test non-container types in _redact_sensitive_data (line 49)
        assert policy._redact_sensitive_data("string") == "string"
        assert policy._redact_sensitive_data(42) == 42

        # Test non-string sensitive values (line 110)
        nested = {"password": "secret123"}
        result = policy._redact_value("api_key", nested)
        assert result["password"] == "secr***"

        # Test successful property access (line 226)
        class WithProperty:
            @property
            def test_prop(self):
                return "prop_value"

        obj = WithProperty()
        result = policy._safe_dump_property(obj, "test_prop")
        assert result == "prop_value"

        # Test streaming iterator redaction (line 65)
        streaming_iterator = ChunkedTextIterator("test", chunk_size=5)
        result = policy._redact_value("data", streaming_iterator)
        assert result["_is_streaming_iterator"] is True

        # Test pydantic object with serialization error (lines 187-188)
        class FailingPydanticObject:
            def model_dump(self, mode=None):
                raise ValueError("Serialization failed")

            def __str__(self):
                return "FailingObject"

        obj = FailingPydanticObject()
        result = policy._dump_pydantic_object(obj)
        assert "_serialization_error" in result
        assert "_str_repr" in result

        # Test object without __dict__ (lines 192-193)
        class NoDict:
            __slots__ = ["value"]

            def __init__(self):
                self.value = "test"

        obj = NoDict()
        result = policy._dump_regular_object(obj)
        assert "_str_repr" in result

        # Test callable attribute (line 217)
        class WithCallable:
            def __init__(self):
                import time

                self.callable_attr = time.time

        obj = WithCallable()
        result = policy._safe_dump_attribute("callable_attr", obj.callable_attr)
        assert "callable" in result

        # Test property handling in _dump_regular_object (lines 204-209)
        class WithRegularProperty:
            def __init__(self):
                self.regular_attr = "regular"

            @property
            def test_property(self):
                return "property_value"

        obj = WithRegularProperty()
        result = policy._dump_regular_object(obj)
        assert result["regular_attr"] == "regular"
        assert result["test_property"] == "property_value"

    def test_exception_handling_paths(self, policy):
        """Test exception handling in object dumping methods."""

        # Test _dump_regular_object exception handling (lines 210-211)
        class ProblematicObject:
            def __init__(self):
                self.attr = "value"

        obj = ProblematicObject()
        original_dir = builtins.dir

        def failing_dir(obj_param):
            if obj_param is obj:
                raise RuntimeError("dir() failed")
            return original_dir(obj_param)

        builtins.dir = failing_dir
        try:
            result = policy._dump_regular_object(obj)
            assert "_str_repr" in result
        finally:
            builtins.dir = original_dir

        # Test _safe_dump_attribute exception handling (lines 219-220)
        class ExceptionValue:
            def __call__(self):
                return "callable"

        exception_value = ExceptionValue()
        policy._safe_dump_recursive = lambda x: (_ for _ in ()).throw(ValueError("Error"))

        result = policy._safe_dump_attribute("key", exception_value)
        assert "<access_error:" in result

        # Test property access error
        class WithFailingProperty:
            @property
            def failing_prop(self):
                raise RuntimeError("Property failed")

        obj = WithFailingProperty()
        result = policy._safe_dump_property(obj, "failing_prop")
        assert "access_error" in result
