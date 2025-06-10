"""Tests for TrackedResponse."""

from unittest.mock import Mock

from luthien_control.core.tracked_context import MutationEvent, TrackedResponse


class TestTrackedResponse:
    """Test TrackedResponse functionality."""

    def test_init(self):
        """Test TrackedResponse initialization."""
        emit_fn = Mock()
        response = TrackedResponse(
            status_code=200,
            headers={"Content-Type": "application/json"},
            content=b'{"result": "success"}',
            emit_fn=emit_fn,
        )

        assert response.status_code == 200
        assert response.get_header("Content-Type") == "application/json"
        assert response.content == b'{"result": "success"}'

    def test_get_headers(self):
        """Test getting all headers."""
        emit_fn = Mock()
        headers = {"Content-Type": "application/json", "X-Custom": "value"}
        response = TrackedResponse(200, headers, b"", emit_fn)

        result = response.get_headers()
        assert result == headers
        # Should be a copy
        assert result is not headers

    def test_get_json(self):
        """Test JSON parsing."""
        emit_fn = Mock()
        content = b'{"choices": [{"message": {"content": "Hello!"}}]}'
        response = TrackedResponse(200, {}, content, emit_fn)

        result = response.get_json()
        expected = {"choices": [{"message": {"content": "Hello!"}}]}
        assert result == expected

    def test_set_status_code(self):
        """Test setting status code emits event."""
        emit_fn = Mock()
        response = TrackedResponse(200, {}, b"", emit_fn)

        response.set_status_code(404)

        # Should emit event
        emit_fn.assert_called_once()
        event = emit_fn.call_args[0][0]
        assert isinstance(event, MutationEvent)
        assert event.operation == "set_status_code"
        assert event.details["old_value"] == 200
        assert event.details["new_value"] == 404

        # Status should be updated
        assert response.status_code == 404

    def test_set_header(self):
        """Test setting a header emits event."""
        emit_fn = Mock()
        response = TrackedResponse(200, {}, b"", emit_fn)

        response.set_header("X-Custom", "test-value")

        # Should emit event
        emit_fn.assert_called_once()
        event = emit_fn.call_args[0][0]
        assert event.operation == "set_header"
        assert event.details["key"] == "X-Custom"
        assert event.details["new_value"] == "test-value"
        assert event.details["old_value"] is None

        # Header should be set
        assert response.get_header("X-Custom") == "test-value"

    def test_remove_header(self):
        """Test removing a header."""
        emit_fn = Mock()
        headers = {"X-Remove": "value", "X-Keep": "value"}
        response = TrackedResponse(200, headers, b"", emit_fn)

        response.remove_header("X-Remove")

        # Should emit event
        emit_fn.assert_called_once()
        event = emit_fn.call_args[0][0]
        assert event.operation == "remove_header"
        assert event.details["key"] == "X-Remove"
        assert event.details["old_value"] == "value"

        # Header should be removed
        assert response.get_header("X-Remove") is None
        assert response.get_header("X-Keep") == "value"

    def test_set_json_content(self):
        """Test setting JSON content."""
        emit_fn = Mock()
        response = TrackedResponse(200, {}, b"old", emit_fn)

        new_data = {"status": "updated", "data": [1, 2, 3]}
        response.set_json_content(new_data)

        # Should emit event
        emit_fn.assert_called_once()
        event = emit_fn.call_args[0][0]
        assert event.operation == "set_json_content"

        # Content should be updated
        assert response.get_json() == new_data
