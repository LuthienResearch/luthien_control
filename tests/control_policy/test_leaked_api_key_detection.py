"""Unit tests for the LeakedApiKeyDetectionPolicy."""

from typing import cast
from unittest.mock import MagicMock

import httpx
import pytest
from luthien_control.control_policy.exceptions import LeakedApiKeyError, NoRequestError
from luthien_control.control_policy.leaked_api_key_detection import LeakedApiKeyDetectionPolicy
from luthien_control.control_policy.serialization import SerializableDict
from luthien_control.core.tracked_context import TrackedContext


@pytest.fixture
def mock_transaction_context() -> TrackedContext:
    """Provides a mock TrackedContext with a mock request object."""
    context = MagicMock(spec=TrackedContext)
    context.transaction_id = "test_tx_id"
    context.request = httpx.Request("POST", "http://example.com/api")
    context.response = None
    context.data = {}  # Add this for consistency with real TrackedContext
    return context


@pytest.fixture
def mock_container() -> MagicMock:
    """Provides a mock DependencyContainer."""
    return MagicMock()


@pytest.fixture
def mock_db_session() -> MagicMock:
    """Provides a mock AsyncSession."""
    return MagicMock()


class TestLeakedApiKeyDetectionPolicyInit:
    """Tests for LeakedApiKeyDetectionPolicy initialization."""

    def test_initialization_with_defaults(self):
        """Test initialization with default values."""
        policy = LeakedApiKeyDetectionPolicy()
        assert policy.name == "LeakedApiKeyDetectionPolicy"
        assert policy.patterns == LeakedApiKeyDetectionPolicy.DEFAULT_PATTERNS
        assert len(policy.compiled_patterns) == len(policy.patterns)

    def test_initialization_with_custom_values(self):
        """Test initialization with custom values."""
        custom_patterns = ["custom-[0-9]+"]
        policy = LeakedApiKeyDetectionPolicy(
            name="CustomDetector",
            patterns=custom_patterns,
        )
        assert policy.name == "CustomDetector"
        assert policy.patterns == custom_patterns
        assert len(policy.compiled_patterns) == len(custom_patterns)


class TestLeakedApiKeyDetectionPolicyApply:
    """Tests for the apply method of LeakedApiKeyDetectionPolicy."""

    @pytest.mark.asyncio
    async def test_apply_no_request_raises_error(self, mock_transaction_context, mock_container, mock_db_session):
        """Test that NoRequestError is raised when no request is in context."""
        mock_transaction_context.request = None
        policy = LeakedApiKeyDetectionPolicy()

        with pytest.raises(NoRequestError, match=r"\[test_tx_id\] No request in context."):
            await policy.apply(mock_transaction_context, mock_container, mock_db_session)

    @pytest.mark.asyncio
    async def test_apply_clean_message_succeeds(self, mock_transaction_context, mock_container, mock_db_session):
        """Test that a message without API keys passes through without issues."""
        body = b"""{
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What is the square root of 64?"}
            ]
        }"""
        # Create httpx.Request with content
        mock_transaction_context.request = httpx.Request("POST", "http://example.com/api", content=body)

        policy = LeakedApiKeyDetectionPolicy()

        result = await policy.apply(mock_transaction_context, mock_container, mock_db_session)

        assert result == mock_transaction_context
        assert result.response is None  # No error response set

    @pytest.mark.asyncio
    async def test_apply_detects_api_key_in_message_content(
        self, mock_transaction_context, mock_container, mock_db_session
    ):
        """Test detection of API key in message content."""
        # Create a request with an API key in the message content
        body = b"""{
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "My API key is sk-abcdefghijklmnopqrstuvwxyz1234567890abcdefghijklmn. Can you help me use it?"}
            ]
        }"""  # noqa: E501 - not worth breaking up a long line in the middle of a multiline string specifying a JSON body
        # Create httpx.Request with content
        mock_transaction_context.request = httpx.Request("POST", "http://example.com/api", content=body)

        policy = LeakedApiKeyDetectionPolicy()

        with pytest.raises(LeakedApiKeyError):
            await policy.apply(mock_transaction_context, mock_container, mock_db_session)

    @pytest.mark.asyncio
    async def test_apply_detects_api_key_in_system_message(
        self, mock_transaction_context, mock_container, mock_db_session
    ):
        """Test detection of API key in system message content."""
        # Create a request with an API key in the system message
        body = b"""{
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant. Use this key: xoxb-1234567890123-1234567890123-AbCdEfGhIjKlMnOpQrStUvWx for authentication."},
                {"role": "user", "content": "Hello, can you help me?"}
            ]
        }"""  # noqa: E501 - not worth breaking up a long line in the middle of a multiline string specifying a JSON body
        # Create httpx.Request with content
        mock_transaction_context.request = httpx.Request("POST", "http://example.com/api", content=body)

        policy = LeakedApiKeyDetectionPolicy()

        with pytest.raises(LeakedApiKeyError):
            await policy.apply(mock_transaction_context, mock_container, mock_db_session)

    @pytest.mark.asyncio
    async def test_apply_with_non_json_body(self, mock_transaction_context, mock_container, mock_db_session):
        """Test that a non-JSON body doesn't cause issues."""
        # Create httpx.Request with non-JSON content
        mock_transaction_context.request = httpx.Request("POST", "http://example.com/api", content=b"Not JSON content")

        policy = LeakedApiKeyDetectionPolicy()

        result = await policy.apply(mock_transaction_context, mock_container, mock_db_session)

        assert result == mock_transaction_context
        assert result.response is None  # No error response set

    @pytest.mark.asyncio
    async def test_apply_with_custom_patterns(self, mock_transaction_context, mock_container, mock_db_session):
        """Test with custom patterns that match message content."""
        # Create a request with a custom pattern to match
        body = b"""{
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "user", "content": "My custom key is custom-12345. Can you help me?"}
            ]
        }"""
        # Create httpx.Request with content
        mock_transaction_context.request = httpx.Request("POST", "http://example.com/api", content=body)

        # Use a custom pattern that matches "custom-" followed by digits
        policy = LeakedApiKeyDetectionPolicy(patterns=["custom-[0-9]+"])

        with pytest.raises(LeakedApiKeyError):
            await policy.apply(mock_transaction_context, mock_container, mock_db_session)

    @pytest.mark.asyncio
    async def test_apply_with_no_content(self, mock_transaction_context, mock_container, mock_db_session):
        """Test that a request with no content doesn't cause issues."""
        # Create httpx.Request with empty content
        mock_transaction_context.request = httpx.Request("POST", "http://example.com/api", content=b"")
        policy = LeakedApiKeyDetectionPolicy()
        result = await policy.apply(mock_transaction_context, mock_container, mock_db_session)
        assert result == mock_transaction_context
        assert result.response is None  # No error response set


class TestLeakedApiKeyDetectionPolicySerialization:
    """Tests for serialization and deserialization of LeakedApiKeyDetectionPolicy."""

    def test_serialize(self):
        """Test serialization of policy configuration."""
        custom_patterns = ["pattern1", "pattern2"]
        policy = LeakedApiKeyDetectionPolicy(
            name="TestSerializer",
            patterns=custom_patterns,
        )

        serialized = policy.serialize()

        assert serialized == {
            "name": "TestSerializer",
            "patterns": custom_patterns,
        }

    def test_from_serialized(self):
        """Test deserialization of policy configuration."""
        config = {
            "name": "DeserializedPolicy",
            "patterns": ["custom-[0-9]+"],
        }

        policy = LeakedApiKeyDetectionPolicy.from_serialized(cast(SerializableDict, config))

        assert policy.name == "DeserializedPolicy"
        assert policy.patterns == ["custom-[0-9]+"]

    def test_from_serialized_with_defaults(self):
        """Test deserialization with minimal config uses defaults."""
        config = {
            "name": "MinimalConfig",
        }

        policy = LeakedApiKeyDetectionPolicy.from_serialized(cast(SerializableDict, config))

        assert policy.name == "MinimalConfig"
        assert policy.patterns == LeakedApiKeyDetectionPolicy.DEFAULT_PATTERNS
