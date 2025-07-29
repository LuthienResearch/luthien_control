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
from luthien_control.core.request import Request
from luthien_control.core.response import Response
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
        api_key="test_key",
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


class TestTransactionContextLoggingPolicy:
    """Test cases for TransactionContextLoggingPolicy."""

    def test_init_with_defaults(self):
        """Test policy initialization with default values."""
        policy = TransactionContextLoggingPolicy()
        assert policy.name == "TransactionContextLoggingPolicy"
        assert policy.log_level == "INFO"
        assert policy.type == "TransactionContextLoggingPolicy"

    def test_init_with_custom_values(self):
        """Test policy initialization with custom values."""
        policy = TransactionContextLoggingPolicy(name="CustomLoggingPolicy", log_level="DEBUG")
        assert policy.name == "CustomLoggingPolicy"
        assert policy.log_level == "DEBUG"
        assert policy.type == "TransactionContextLoggingPolicy"

    def test_init_with_invalid_values(self):
        """Test policy initialization handles invalid input gracefully."""
        # The policy should still initialize even with unusual log levels
        # as validation happens at logging time
        policy = TransactionContextLoggingPolicy(log_level="INVALID")
        assert policy.log_level == "INVALID"

    def test_redact_api_key_field(self):
        """Test that API key fields are properly redacted."""
        policy = TransactionContextLoggingPolicy()

        test_cases = [
            ("api_key", "sk-1234567890abcdefghijklmnop", "sk-1***"),
            ("apikey", "abcd1234567890", "abcd***"),
            ("api-key", "short", "***"),
            ("API_KEY", "LONG_API_KEY_VALUE", "LONG***"),
        ]

        for key, value, expected in test_cases:
            result = policy._redact_value(key, value)
            assert result == expected

    def test_redact_authorization_field(self):
        """Test that authorization fields are properly redacted."""
        policy = TransactionContextLoggingPolicy()

        test_cases = [
            ("authorization", "Bearer sk-1234567890abcdefghijklmnop", "Bearer ***"),
            ("Authorization", "Bearer token123", "Bearer ***"),
            ("bearer", "sk-abcdefghijklmnop", "sk-a***"),  # 17 chars
            ("token", "very_long_token_value", "very***"),  # 20 chars
        ]

        for key, value, expected in test_cases:
            result = policy._redact_value(key, value)
            assert result == expected

    def test_redact_password_fields(self):
        """Test that password fields are properly redacted."""
        policy = TransactionContextLoggingPolicy()

        test_cases = [
            ("password", "secret123", "secr***"),  # 9 chars
            ("passwd", "my_password", "my_p***"),  # 11 chars
            ("pwd", "short", "***"),  # 5 chars
            ("secret", "top_secret_value", "top_***"),  # 16 chars
        ]

        for key, value, expected in test_cases:
            result = policy._redact_value(key, value)
            assert result == expected

    def test_redact_bearer_token_patterns(self):
        """Test that Bearer token patterns in values are redacted."""
        policy = TransactionContextLoggingPolicy()

        test_cases = [
            ("header", "Bearer sk-1234567890abcdef", "Bearer ***"),
            ("auth_header", "bearer token123456", "bearer ***"),
            ("custom", "Authorization: Bearer sk-abcdef", "Authorization: Bearer ***"),
        ]

        for key, value, expected in test_cases:
            result = policy._redact_value(key, value)
            assert result == expected

    def test_preserve_non_sensitive_data(self):
        """Test that non-sensitive data is preserved."""
        policy = TransactionContextLoggingPolicy()

        test_cases = [
            ("user_id", "12345", "12345"),
            ("name", "John Doe", "John Doe"),
            ("model", "gpt-4", "gpt-4"),
            ("timestamp", "2023-01-01T00:00:00Z", "2023-01-01T00:00:00Z"),
            ("count", 42, 42),
            ("enabled", True, True),
        ]

        for key, value, expected in test_cases:
            result = policy._redact_value(key, value)
            assert result == expected

    def test_redact_nested_structures(self):
        """Test that nested data structures are properly redacted."""
        policy = TransactionContextLoggingPolicy()

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

    def test_serialize_transaction_context_with_openai_request(self, sample_transaction):
        """Test serialization of transaction with OpenAI request."""
        policy = TransactionContextLoggingPolicy()

        # Add API key to the request
        sample_transaction.openai_request.api_key = "sk-test123456789"

        context = policy._serialize_transaction_context(sample_transaction)

        assert "transaction_id" in context
        assert "request_type" in context
        assert "openai_request" in context
        assert context["openai_request"]["api_key"] == "sk-t***"

    def test_serialize_transaction_context_with_raw_request(self):
        """Test serialization of transaction with raw request."""
        from luthien_control.core.raw_request import RawRequest

        policy = TransactionContextLoggingPolicy()

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

    def test_serialize_transaction_context_with_transaction_data(self, sample_transaction):
        """Test serialization includes transaction data with redaction."""
        policy = TransactionContextLoggingPolicy()

        # Add some custom data to transaction
        sample_transaction.data["user_id"] = "12345"
        sample_transaction.data["secret_key"] = "very_secret_value"
        sample_transaction.data["api_key"] = "sk-abcdefghijklmnop"

        context = policy._serialize_transaction_context(sample_transaction)

        assert "transaction_data" in context
        assert context["transaction_data"]["user_id"] == "12345"
        assert context["transaction_data"]["secret_key"] == "very***"
        assert context["transaction_data"]["api_key"] == "sk-a***"

    @pytest.mark.asyncio
    async def test_apply_logs_transaction_context(self, sample_transaction, caplog):
        """Test that apply method logs transaction context."""
        policy = TransactionContextLoggingPolicy(log_level="INFO")
        container = MagicMock(spec=DependencyContainer)
        session = MagicMock(spec=AsyncSession)

        with caplog.at_level(logging.INFO):
            result = await policy.apply(sample_transaction, container, session)

        # Should return the same transaction unchanged
        assert result is sample_transaction

        # Should have logged the transaction context as JSON
        assert len(caplog.records) == 1
        assert "Transaction Context JSON:" in caplog.records[0].message
        assert str(sample_transaction.transaction_id) in caplog.records[0].message

    @pytest.mark.asyncio
    async def test_apply_with_debug_log_level(self, sample_transaction, caplog):
        """Test apply method with DEBUG log level."""
        policy = TransactionContextLoggingPolicy(log_level="DEBUG")
        container = MagicMock(spec=DependencyContainer)
        session = MagicMock(spec=AsyncSession)

        with caplog.at_level(logging.DEBUG):
            await policy.apply(sample_transaction, container, session)

        assert len(caplog.records) == 1
        assert caplog.records[0].levelno == logging.DEBUG

    @pytest.mark.asyncio
    async def test_apply_handles_serialization_errors(self, sample_transaction, caplog):
        """Test that apply method handles serialization errors gracefully."""
        policy = TransactionContextLoggingPolicy()
        container = MagicMock(spec=DependencyContainer)
        session = MagicMock(spec=AsyncSession)

        # Mock the serialization method to raise an exception
        def mock_serialize_error(transaction):
            raise ValueError("Serialization failed")

        policy._serialize_transaction_context = mock_serialize_error

        with caplog.at_level(logging.ERROR):
            result = await policy.apply(sample_transaction, container, session)

        # Should still return the transaction
        assert result is sample_transaction

        # Should log the error
        assert len(caplog.records) == 1
        assert "Failed to log transaction context" in caplog.records[0].message
        assert caplog.records[0].levelno == logging.ERROR

    def test_serialization_and_deserialization(self):
        """Test that policy can be serialized and deserialized."""
        original_policy = TransactionContextLoggingPolicy(name="TestLoggingPolicy", log_level="WARNING")

        # Serialize
        serialized = original_policy.serialize()
        assert isinstance(serialized, dict)
        assert serialized["type"] == "TransactionContextLoggingPolicy"
        assert serialized["name"] == "TestLoggingPolicy"
        assert serialized["log_level"] == "WARNING"

        # Deserialize
        deserialized_policy = TransactionContextLoggingPolicy.from_serialized(serialized)
        assert deserialized_policy.name == original_policy.name
        assert deserialized_policy.log_level == original_policy.log_level
        assert deserialized_policy.type == original_policy.type

    def test_serialization_with_minimal_config(self):
        """Test serialization with minimal configuration."""
        config: SerializableDict = {"type": "TransactionContextLoggingPolicy"}

        policy = TransactionContextLoggingPolicy.from_serialized(config)
        assert policy.name == "TransactionContextLoggingPolicy"
        assert policy.log_level == "INFO"

    def test_get_policy_type_name(self):
        """Test that get_policy_type_name returns correct type."""
        assert TransactionContextLoggingPolicy.get_policy_type_name() == "TransactionContextLoggingPolicy"

    def test_redact_common_api_key_patterns(self):
        """Test redaction of common API key patterns."""
        policy = TransactionContextLoggingPolicy()

        # Test OpenAI style keys
        openai_key = "sk-1234567890abcdefghijklmnopqrstuvwxyz"
        result = policy._redact_value("some_field", openai_key)
        assert result == "sk-1***"

        # Test long generic keys
        generic_key = "abcdefghijklmnopqrstuvwxyz123456"
        result = policy._redact_value("some_field", generic_key)
        # Should not be redacted unless field name is sensitive
        assert result == generic_key

        # But should be redacted if field name is sensitive
        result = policy._redact_value("api_key", generic_key)
        assert result == "abcd***"

    def test_edge_cases_for_redaction(self):
        """Test edge cases in redaction logic."""
        policy = TransactionContextLoggingPolicy()

        # Empty strings
        assert policy._redact_value("api_key", "") == ""

        # None values
        assert policy._redact_value("api_key", None) is None

        # Non-string types
        assert policy._redact_value("api_key", 12345) == 12345
        assert policy._redact_value("api_key", True) is True
        assert policy._redact_value("api_key", []) == []

        # Very short strings
        assert policy._redact_value("password", "a") == "***"
        assert policy._redact_value("password", "ab") == "***"

    def test_safe_model_dump_with_pydantic_object(self, sample_transaction):
        """Test _safe_model_dump with a Pydantic object."""
        policy = TransactionContextLoggingPolicy()

        result = policy._safe_model_dump(sample_transaction.openai_request)
        assert isinstance(result, dict)
        assert "api_key" in result
        assert "payload" in result

    def test_safe_model_dump_with_object_without_model_dump(self):
        """Test _safe_model_dump with an object that doesn't have model_dump."""
        policy = TransactionContextLoggingPolicy()

        class SimpleObject:
            def __init__(self):
                self.name = "test"
                self.value = 42

        obj = SimpleObject()
        result = policy._safe_model_dump(obj)

        assert isinstance(result, dict)
        assert "name" in result
        assert "value" in result
        assert result["name"] == "test"
        assert result["value"] == 42

    def test_safe_model_dump_with_object_that_fails_model_dump(self):
        """Test _safe_model_dump with an object where model_dump fails."""
        policy = TransactionContextLoggingPolicy()

        class ProblematicObject:
            def model_dump(self, mode=None):
                raise ValueError("Serialization failed")

            def __str__(self):
                return "ProblematicObject instance"

        obj = ProblematicObject()
        result = policy._safe_model_dump(obj)

        assert isinstance(result, dict)
        assert "_serialization_error" in result
        assert "_str_repr" in result
        assert "model_dump failed" in result["_serialization_error"]

    def test_safe_model_dump_with_primitive_object(self):
        """Test _safe_model_dump with a primitive object."""
        policy = TransactionContextLoggingPolicy()

        result = policy._safe_model_dump("simple string")
        assert isinstance(result, dict)
        assert "_str_repr" in result
        assert result["_str_repr"] == "simple string"
