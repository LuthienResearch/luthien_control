"""Tests for dual-mode transaction functionality."""

import pytest
from luthien_control.api.openai_chat_completions.datatypes import Message
from luthien_control.api.openai_chat_completions.request import OpenAIChatCompletionsRequest
from luthien_control.core.raw_request import RawRequest
from luthien_control.core.request import Request
from luthien_control.core.request_type import RequestType
from luthien_control.core.transaction import Transaction
from psygnal.containers import EventedList


class TestDualModeTransaction:
    """Test cases for dual-mode transaction functionality."""

    def test_openai_transaction_creation(self):
        """Test creating a transaction with OpenAI request."""
        openai_request = OpenAIChatCompletionsRequest(
            model="gpt-3.5-turbo", messages=EventedList([Message(role="user", content="Hello")])
        )

        request = Request(payload=openai_request, api_endpoint="https://api.openai.com", api_key="test-key")

        transaction = Transaction(openai_request=request)

        assert transaction.request_type == RequestType.OPENAI_CHAT
        assert transaction.openai_request is not None
        assert transaction.raw_request is None
        assert transaction.openai_response is None
        assert transaction.raw_response is None

    def test_raw_transaction_creation(self):
        """Test creating a transaction with raw request."""
        raw_request = RawRequest(
            method="GET", path="v1/models", headers={"Content-Type": "application/json"}, api_key="test-key"
        )

        transaction = Transaction(raw_request=raw_request)

        assert transaction.request_type == RequestType.RAW_PASSTHROUGH
        assert transaction.raw_request is not None
        assert transaction.openai_request is None
        assert transaction.raw_response is None
        assert transaction.openai_response is None

    def test_empty_transaction_validation(self):
        """Test that creating a transaction with no request raises an error."""
        with pytest.raises(ValueError, match="must have either openai_request or raw_request"):
            Transaction()

    def test_dual_request_validation(self):
        """Test that creating a transaction with both request types raises an error."""
        openai_request = Request(
            payload=OpenAIChatCompletionsRequest(
                model="gpt-3.5-turbo", messages=EventedList([Message(role="user", content="Hello")])
            ),
            api_endpoint="https://api.openai.com",
            api_key="test-key",
        )

        raw_request = RawRequest(method="GET", path="v1/models", api_key="test-key")

        with pytest.raises(ValueError, match="cannot have both openai_request and raw_request"):
            Transaction(
                openai_request=openai_request,
                raw_request=raw_request,
            )

    def test_request_type_property(self):
        """Test the request_type property returns correct values."""
        # Test OpenAI transaction
        openai_transaction = Transaction(
            openai_request=Request(
                payload=OpenAIChatCompletionsRequest(
                    model="gpt-3.5-turbo", messages=EventedList([Message(role="user", content="Hello")])
                ),
                api_endpoint="https://api.openai.com",
                api_key="test-key",
            )
        )
        assert openai_transaction.request_type == RequestType.OPENAI_CHAT

        # Test raw transaction
        raw_transaction = Transaction(raw_request=RawRequest(method="GET", path="v1/models", api_key="test-key"))
        assert raw_transaction.request_type == RequestType.RAW_PASSTHROUGH
