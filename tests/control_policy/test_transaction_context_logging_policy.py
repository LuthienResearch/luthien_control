import logging
from unittest.mock import MagicMock

import pytest
from luthien_control.api.openai_chat_completions.datatypes import Choice, Message, Usage
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.api.openai_chat_completions.response import OpenAIChatCompletionsResponse
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.control_policy.transaction_context_logging_policy import (
    TransactionContextLoggingPolicy,
)
from luthien_control.core.dependency_container import DependencyContainer
from luthien_control.core.raw_request import RawRequest
from luthien_control.core.request import Request
from luthien_control.core.response import Response
from luthien_control.core.streaming_response import ChunkedTextIterator
from luthien_control.core.transaction import Transaction
from psygnal.containers import EventedList
from sqlalchemy.ext.asyncio import AsyncSession


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
    container = MagicMock(spec=DependencyContainer)
    session = MagicMock(spec=AsyncSession)
    return container, session


@pytest.fixture
def policy():
    """Provides a policy instance for testing."""
    return TransactionContextLoggingPolicy()


class TestTransactionContextLoggingPolicy:
    """Test cases for TransactionContextLoggingPolicy."""

    @pytest.mark.parametrize(
        "name,log_level,expected_name,expected_level",
        [
            (None, None, "TransactionContextLoggingPolicy", "INFO"),
            ("CustomLoggingPolicy", "DEBUG", "CustomLoggingPolicy", "DEBUG"),
            (None, "WARNING", "TransactionContextLoggingPolicy", "WARNING"),
        ],
    )
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

    @pytest.mark.parametrize(
        "field_name,value,expected",
        [
            # API key patterns
            ("api_key", "sk-1234567890abcdefghijklmnop", "sk-1***"),
            ("apikey", "abcd1234567890", "abcd***"),
            ("api-key", "short", "***"),
            ("API_KEY", "LONG_API_KEY_VALUE", "LONG***"),
            # Authorization patterns
            ("authorization", "Bearer sk-1234567890abcdefghijklmnop", "Bearer ***"),
            ("Authorization", "Bearer token123", "Bearer ***"),
            ("bearer", "sk-abcdefghijklmnop", "sk-a***"),
            ("token", "very_long_token_value", "very***"),
            # Password patterns
            ("password", "secret123", "secr***"),
            ("passwd", "my_password", "my_p***"),
            ("pwd", "short", "***"),
            ("secret", "top_secret_value", "top_***"),
            # Bearer token in values
            ("header", "Bearer sk-1234567890abcdef", "Bearer ***"),
            ("auth_header", "bearer token123456", "bearer ***"),
            ("custom", "Authorization: Bearer sk-abcdef", "Authorization: Bearer ***"),
        ],
    )
    def test_sensitive_data_redaction(self, policy, field_name, value, expected):
        """Test that sensitive data fields are properly redacted."""
        result = policy._redact_value(field_name, value)
        assert result == expected

    @pytest.mark.parametrize(
        "field_name,value",
        [
            ("user_id", "12345"),
            ("name", "John Doe"),
            ("model", "gpt-4"),
            ("timestamp", "2023-01-01T00:00:00Z"),
            ("count", 42),
            ("enabled", True),
            ("api_key", ""),  # Empty string
            ("api_key", None),  # None value
            ("password", "a"),  # Very short string
        ],
    )
    def test_non_sensitive_data_preserved(self, policy, field_name, value):
        """Test that non-sensitive data is preserved or handled safely."""
        result = policy._redact_value(field_name, value)
        if field_name in ["api_key", "password"] and isinstance(value, str) and value and len(value) <= 2:
            assert result == "***"
        elif value is None or (isinstance(value, str) and not value):
            assert result == value
        else:
            assert result == value

    def test_nested_structure_redaction(self, policy):
        """Test that nested data structures are properly redacted."""
        data = {
            "user_info": {"name": "John Doe", "api_key": "sk-1234567890abcdef"},
            "headers": [
                {"name": "Content-Type", "value": "application/json"},
                {"name": "Authorization", "value": "Bearer secret_token"},
            ],
            "config": {"database": {"host": "localhost", "password": "db_secret_password"}},
        }

        result = policy._redact_sensitive_data(data)

        assert result["user_info"]["name"] == "John Doe"
        assert result["user_info"]["api_key"] == "sk-1***"
        assert result["headers"][0]["value"] == "application/json"
        assert result["headers"][1]["value"] == "Bearer ***"
        assert result["config"]["database"]["host"] == "localhost"
        assert result["config"]["database"]["password"] == "db_s***"

    def test_transaction_serialization_with_openai(self, policy, sample_transaction):
        """Test serialization of transaction with OpenAI request."""
        context = policy._serialize_transaction_context(sample_transaction)

        assert "transaction_id" in context
        assert "request_type" in context
        assert "openai_request" in context
        assert context["openai_request"]["api_key"] == "sk-t***"

    def test_transaction_serialization_with_raw_request(self, policy):
        """Test serialization of transaction with raw request."""
        raw_request = RawRequest(
            method="POST",
            path="/chat",
            api_key="sk-test123456789",
            headers={"Authorization": "Bearer secret_token"},
            body=b'{"model": "gpt-4", "messages": []}',
        )

        transaction = Transaction(raw_request=raw_request)
        context = policy._serialize_transaction_context(transaction)

        assert "transaction_id" in context
        assert "raw_request" in context
        assert context["raw_request"]["headers"]["Authorization"] == "Bearer ***"

    def test_transaction_data_serialization(self, policy, sample_transaction):
        """Test serialization includes transaction data with redaction."""
        sample_transaction.data.update(
            {"user_id": "12345", "secret_key": "very_secret_value", "api_key": "sk-abcdefghijklmnop"}
        )

        context = policy._serialize_transaction_context(sample_transaction)

        assert "transaction_data" in context
        data = context["transaction_data"]
        assert data["user_id"] == "12345"
        assert data["secret_key"] == "very***"
        assert data["api_key"] == "sk-a***"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "log_level,expected_level",
        [
            ("INFO", logging.INFO),
            ("DEBUG", logging.DEBUG),
            ("WARNING", logging.WARNING),
        ],
    )
    async def test_apply_logs_transaction_context(
        self, sample_transaction, mock_dependencies, caplog, log_level, expected_level
    ):
        """Test that apply method logs transaction context at specified level."""
        policy = TransactionContextLoggingPolicy(log_level=log_level)
        container, session = mock_dependencies

        with caplog.at_level(expected_level):
            result = await policy.apply(sample_transaction, container, session)

        assert result is sample_transaction
        assert len(caplog.records) == 1
        assert "Transaction Context JSON:" in caplog.records[0].message
        assert caplog.records[0].levelno == expected_level

    @pytest.mark.asyncio
    async def test_apply_handles_serialization_errors(self, sample_transaction, mock_dependencies, caplog):
        """Test that apply method handles serialization errors gracefully."""
        policy = TransactionContextLoggingPolicy()
        container, session = mock_dependencies

        # Mock serialization to fail
        policy._serialize_transaction_context = lambda transaction: (_ for _ in ()).throw(
            ValueError("Serialization failed")
        )

        with caplog.at_level(logging.ERROR):
            result = await policy.apply(sample_transaction, container, session)

        assert result is sample_transaction
        assert len(caplog.records) == 1
        assert "Failed to log transaction context" in caplog.records[0].message

    def test_policy_serialization(self):
        """Test policy serialization and deserialization."""
        original = TransactionContextLoggingPolicy(name="TestLoggingPolicy", log_level="WARNING")

        serialized = original.serialize()
        assert serialized["type"] == "TransactionContextLoggingPolicy"
        assert serialized["name"] == "TestLoggingPolicy"
        assert serialized["log_level"] == "WARNING"

        deserialized = TransactionContextLoggingPolicy.from_serialized(serialized)
        assert deserialized.name == original.name
        assert deserialized.log_level == original.log_level

    def test_minimal_serialization_config(self):
        """Test deserialization with minimal configuration."""
        config: SerializableDict = {"type": "TransactionContextLoggingPolicy"}
        policy = TransactionContextLoggingPolicy.from_serialized(config)
        assert policy.name == "TransactionContextLoggingPolicy"

    def test_api_key_pattern_recognition(self, policy):
        """Test recognition and redaction of API key patterns."""
        # OpenAI-style key should be redacted by pattern
        openai_key = "sk-1234567890abcdefghijklmnopqrstuvwxyz"
        result = policy._redact_value("some_field", openai_key)
        assert result == "sk-1***"

        # Generic key should only be redacted when field name is sensitive
        generic_key = "abcdefghijklmnopqrstuvwxyz123456"
        assert policy._redact_value("some_field", generic_key) == generic_key
        assert policy._redact_value("api_key", generic_key) == "abcd***"

    @pytest.mark.parametrize(
        "test_obj,expected_keys",
        [
            # Pydantic object
            ("pydantic", ["api_key", "payload"]),
            # Simple object
            ("simple", ["name", "value"]),
            # Primitive
            ("primitive", ["_str_repr"]),
            # Failing model_dump
            ("failing", ["_serialization_error", "_str_repr"]),
        ],
    )
    def test_safe_model_dump_scenarios(self, policy, sample_transaction, test_obj, expected_keys):
        """Test _safe_model_dump with various object types."""
        if test_obj == "pydantic":
            obj = sample_transaction.openai_request
        elif test_obj == "simple":

            class SimpleObject:
                def __init__(self):
                    self.name = "test"
                    self.value = 42

            obj = SimpleObject()
        elif test_obj == "primitive":
            obj = "simple string"
        elif test_obj == "failing":

            class FailingObject:
                def model_dump(self, mode=None):
                    raise ValueError("Serialization failed")

                def __str__(self):
                    return "FailingObject instance"

            obj = FailingObject()
        else:
            obj = None

        result = policy._safe_model_dump(obj)
        assert isinstance(result, dict)
        for key in expected_keys:
            assert key in result

    def test_safe_model_dump_with_streaming_object(self, policy):
        """Test _safe_model_dump handles streaming-like objects safely."""

        class StreamingObject:
            def __init__(self):
                self.normal_attr = "normal_value"
                self._private_attr = "ignored"
                import time

                self.callable_attr = time.time

        obj = StreamingObject()
        result = policy._safe_model_dump(obj)

        assert result["normal_attr"] == "normal_value"
        assert "_private_attr" not in result
        assert "callable" in result["callable_attr"]

    def test_streaming_response_logging(self, policy):
        """Test that streaming responses are logged correctly."""
        # Create a transaction with streaming response
        request = Request(
            payload=OpenAIChatCompletionsRequest(
                model="gpt-4",
                messages=EventedList([Message(role="user", content="Hello, world!")]),
                stream=True,
            ),
            api_endpoint="https://api.openai.com/v1/chat/completions",
            api_key="sk-test123456789",
        )

        # Create streaming response
        streaming_iterator = ChunkedTextIterator("Hello world", chunk_size=5)
        response = Response(streaming_iterator=streaming_iterator)

        transaction = Transaction(openai_request=request, openai_response=response)

        # Serialize the transaction
        context = policy._serialize_transaction_context(transaction)

        # Check that streaming info is captured
        assert "openai_response" in context
        response_data = context["openai_response"]
        assert response_data["is_streaming"] is True
        assert "streaming_iterator" in response_data

        # Check streaming iterator metadata
        iterator_data = response_data["streaming_iterator"]
        assert iterator_data["_is_streaming_iterator"] is True
        assert iterator_data["_iterator_type"] == "ChunkedTextIterator"
        assert iterator_data["_chunk_size"] == 5

    def test_safe_model_dump_with_streaming_iterator(self, policy):
        """Test _safe_model_dump handles StreamingResponseIterator objects."""
        streaming_iterator = ChunkedTextIterator("test text", chunk_size=10)

        result = policy._safe_model_dump(streaming_iterator)

        assert result["_is_streaming_iterator"] is True
        assert result["_iterator_type"] == "ChunkedTextIterator"
        assert result["_chunk_size"] == 10
        assert result["_position"] == 0

    def test_safe_model_dump_with_object_property_access_error(self, policy):
        """Test _safe_model_dump handles objects with properties that raise exceptions."""

        class ProblematicObject:
            def __init__(self):
                self.normal_attr = "normal"
                self._private = "private"

            @property
            def failing_property(self):
                raise RuntimeError("Property access failed")

        obj = ProblematicObject()
        result = policy._safe_model_dump(obj)

        assert result["normal_attr"] == "normal"
        assert "_private" not in result
        assert "access_error" in result["failing_property"]

    def test_redact_value_with_nested_streaming_iterator(self, policy):
        """Test _redact_value handles nested streaming iterators correctly."""
        streaming_iterator = ChunkedTextIterator("test", chunk_size=5)

        # Test with streaming iterator as value in nested structure
        result = policy._redact_value("data", streaming_iterator)

        assert result["_is_streaming_iterator"] is True
        assert result["_iterator_type"] == "ChunkedTextIterator"

    def test_transaction_serialization_with_raw_response_streaming(self, policy):
        """Test serialization includes raw response streaming iterator."""
        from luthien_control.core.raw_request import RawRequest
        from luthien_control.core.raw_response import RawResponse

        # Create raw request (required for Transaction)
        raw_request = RawRequest(
            method="GET",
            path="v1/models",
            headers={"Accept": "text/event-stream"},
            body=b"",
            api_key="test-key",
            backend_url="https://api.example.com",
        )

        # Create raw response with streaming iterator
        streaming_iterator = ChunkedTextIterator("raw response data", chunk_size=8)
        raw_response = RawResponse(
            status_code=200, headers={"content-type": "text/event-stream"}, streaming_iterator=streaming_iterator
        )

        transaction = Transaction(raw_request=raw_request, raw_response=raw_response)
        context = policy._serialize_transaction_context(transaction)

        assert "raw_response" in context
        response_data = context["raw_response"]
        assert response_data["is_streaming"] is True
        assert "streaming_iterator" in response_data

        # Check streaming iterator metadata
        iterator_data = response_data["streaming_iterator"]
        assert iterator_data["_is_streaming_iterator"] is True
        assert iterator_data["_iterator_type"] == "ChunkedTextIterator"
