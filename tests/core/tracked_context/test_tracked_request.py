"""Tests for TrackedRequest."""

import json
from unittest.mock import Mock

import pytest
from luthien_control.core.tracked_context import MutationEvent, TrackedRequest


class TestTrackedRequest:
    """Test TrackedRequest functionality."""

    def test_init(self):
        """Test TrackedRequest initialization."""
        emit_fn = Mock()
        request = TrackedRequest(
            method="POST",
            url="https://api.example.com/chat",
            headers={"Content-Type": "application/json"},
            content=b'{"message": "hello"}',
            emit_fn=emit_fn,
        )

        assert request.method == "POST"
        assert request.url == "https://api.example.com/chat"
        assert request.get_header("Content-Type") == "application/json"
        assert request.content == b'{"message": "hello"}'

    def test_get_headers(self):
        """Test getting all headers."""
        emit_fn = Mock()
        headers = {"Content-Type": "application/json", "Authorization": "Bearer token"}
        request = TrackedRequest("GET", "http://test.com", headers, b"", emit_fn)

        result = request.get_headers()
        assert result == headers
        # Should be a copy, not the same object
        assert result is not headers

    def test_get_json(self):
        """Test JSON parsing."""
        emit_fn = Mock()
        content = b'{"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]}'
        request = TrackedRequest("POST", "http://test.com", {}, content, emit_fn)

        result = request.get_json()
        expected = {"model": "gpt-4", "messages": [{"role": "user", "content": "hi"}]}
        assert result == expected

    def test_get_json_invalid(self):
        """Test JSON parsing with invalid content."""
        emit_fn = Mock()
        request = TrackedRequest("POST", "http://test.com", {}, b"invalid json", emit_fn)

        with pytest.raises(json.JSONDecodeError):
            request.get_json()

    def test_set_header(self):
        """Test setting a header emits event."""
        emit_fn = Mock()
        request = TrackedRequest("GET", "http://test.com", {}, b"", emit_fn)

        request.set_header("Authorization", "Bearer new-token")

        # Should emit event
        emit_fn.assert_called_once()
        event = emit_fn.call_args[0][0]
        assert isinstance(event, MutationEvent)
        assert event.operation == "set_header"
        assert event.details["key"] == "Authorization"
        assert event.details["new_value"] == "Bearer new-token"
        assert event.details["old_value"] is None

        # Header should be set
        assert request.get_header("Authorization") == "Bearer new-token"

    def test_set_header_replace(self):
        """Test replacing an existing header."""
        emit_fn = Mock()
        headers = {"Authorization": "Bearer old-token"}
        request = TrackedRequest("GET", "http://test.com", headers, b"", emit_fn)

        request.set_header("Authorization", "Bearer new-token")

        # Should track old value
        event = emit_fn.call_args[0][0]
        assert event.details["old_value"] == "Bearer old-token"
        assert event.details["new_value"] == "Bearer new-token"

    def test_remove_header(self):
        """Test removing a header."""
        emit_fn = Mock()
        headers = {"Authorization": "Bearer token", "Content-Type": "application/json"}
        request = TrackedRequest("GET", "http://test.com", headers, b"", emit_fn)

        request.remove_header("Authorization")

        # Should emit event
        emit_fn.assert_called_once()
        event = emit_fn.call_args[0][0]
        assert event.operation == "remove_header"
        assert event.details["key"] == "Authorization"
        assert event.details["old_value"] == "Bearer token"

        # Header should be removed
        assert request.get_header("Authorization") is None
        assert request.get_header("Content-Type") == "application/json"

    def test_remove_nonexistent_header(self):
        """Test removing a header that doesn't exist."""
        emit_fn = Mock()
        request = TrackedRequest("GET", "http://test.com", {}, b"", emit_fn)

        request.remove_header("NonExistent")

        # Should not emit event for non-existent header
        emit_fn.assert_not_called()

    def test_set_json_content(self):
        """Test setting JSON content."""
        emit_fn = Mock()
        request = TrackedRequest("POST", "http://test.com", {}, b"old content", emit_fn)

        new_data = {"model": "gpt-4", "temperature": 0.7}
        request.set_json_content(new_data)

        # Should emit event
        emit_fn.assert_called_once()
        event = emit_fn.call_args[0][0]
        assert event.operation == "set_json_content"

        # Content should be updated
        assert request.get_json() == new_data
