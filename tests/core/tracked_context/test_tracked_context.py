"""Tests for TrackedContext."""

import uuid
from unittest.mock import Mock

from luthien_control.core.tracked_context import TrackedContext


class TestTrackedContext:
    """Test TrackedContext functionality."""

    def test_init(self):
        """Test TrackedContext initialization."""
        context = TrackedContext()

        assert isinstance(context.transaction_id, uuid.UUID)
        assert context.request is None
        assert context.response is None

    def test_init_with_transaction_id(self):
        """Test initialization with specific transaction ID."""
        tx_id = uuid.uuid4()
        context = TrackedContext(transaction_id=tx_id)

        assert context.transaction_id == tx_id

    def test_add_listener(self):
        """Test adding event listeners."""
        context = TrackedContext()
        listener = Mock()

        context.events.mutation.register("TrackedContext.set_data", listener)
        # Should not raise - internal state tracking

    def test_set_request(self):
        """Test setting request."""
        context = TrackedContext()

        context.update_request(
            method="POST",
            url="https://api.test.com",
            headers={"Content-Type": "application/json"},
            content=b'{"test": true}',
        )

        # context.request returns a copy, not the same object
        assert context.request is not None
        assert context.request.method == "POST"
        assert str(context.request.url) == "https://api.test.com"

    def test_set_response(self):
        """Test setting response."""
        context = TrackedContext()

        context.update_response(
            status_code=200, headers={"Content-Type": "application/json"}, content=b'{"success": true}'
        )

        # context.response returns a copy, not the same object
        assert context.response is not None
        assert context.response.status_code == 200

    def test_data_operations(self):
        """Test data get/set operations."""
        context = TrackedContext()

        # Test setting data
        context.set_data("user_id", "12345")
        assert context.get_data("user_id") == "12345"

        # Test default value
        assert context.get_data("nonexistent", "default") == "default"

        # Test get_all_data
        context.set_data("another_key", "value")
        all_data = context.get_all_data()
        assert all_data["user_id"] == "12345"
        assert all_data["another_key"] == "value"

    def test_event_emission(self):
        """Test that events are emitted to listeners."""
        context = TrackedContext()
        listener = Mock()
        context.events.mutation.register("test_listener", listener)

        # Set data should emit event
        context.set_data("test_key", "test_value")

        # Listener should be called with (event_type, data)
        listener.assert_called_once()
        event_type = listener.call_args[0][0]
        data = listener.call_args[0][1]

        assert event_type == "context_mutation"
        assert data.operation == "set_data"
        assert data.details["key"] == "test_key"
        assert data.details["new_value"] == "test_value"

    def test_update_request_partial(self):
        """Test partial request update."""
        context = TrackedContext()

        # First set a complete request
        context.update_request(
            method="GET",
            url="https://api.test.com/v1",
            headers={"Authorization": "Bearer token"},
            content=b"initial",
            from_scratch=True,
        )

        # Update only some fields
        context.update_request(
            method="POST", headers={"Content-Type": "application/json"}, preserve_existing_headers=False
        )

        # Check that method and headers were updated, but url and content remain
        req = context.request
        assert req is not None
        assert req.method == "POST"
        assert str(req.url) == "https://api.test.com/v1"
        assert req.headers["Content-Type"] == "application/json"
        assert req.headers.get("Authorization") is None  # Headers replaced, not merged
        assert req.content == b"initial"

    def test_update_request_from_scratch(self):
        """Test request update with from_scratch=True."""
        context = TrackedContext()

        # Set initial request
        context.update_request(
            method="GET", url="https://api.test.com", headers={"Authorization": "Bearer token"}, content=b"initial"
        )

        # Update from scratch with minimal data
        context.update_request(url="https://api.new.com", method="GET", from_scratch=True)

        # Check that only url is set, other fields are defaults
        req = context.request
        assert req is not None
        assert req.method == "GET"  # Default method
        assert str(req.url) == "https://api.new.com"
        assert req.headers == {"host": "api.new.com"}  # Empty headers
        assert req.content == b""  # Empty content

    def test_update_response_partial(self):
        """Test partial response update."""
        context = TrackedContext()

        # First set a complete response
        context.update_response(
            status_code=200, headers={"Content-Type": "application/json"}, content=b'{"result": "success"}'
        )

        # Update only status code
        context.update_response(status_code=404)

        # Check that only status_code was updated
        resp = context.response
        assert resp is not None
        assert resp.status_code == 404
        assert resp.headers["Content-Type"] == "application/json"
        assert resp.content == b'{"result": "success"}'

    def test_update_response_from_scratch(self):
        """Test response update with from_scratch=True."""
        context = TrackedContext()

        # Set initial response
        context.update_response(status_code=200, headers={"Content-Type": "application/json"}, content=b'{"old": true}')

        # Update from scratch with minimal data
        context.update_response(status_code=500, from_scratch=True)

        # Check that only status_code is set, other fields are defaults
        resp = context.response
        assert resp is not None
        assert resp.status_code == 500
        assert resp.headers == {}  # Empty headers
        assert resp.content == b""  # Empty content

    def test_update_request_when_response_exists(self):
        """Test that updating request after response is set works correctly."""
        context = TrackedContext()

        # Set response first
        context.update_response(status_code=200, content=b"response")

        # Update request
        context.update_request(method="POST", url="https://api.test.com")

        # Both should exist
        assert context.request is not None
        assert context.response is not None
        assert context.request.method == "POST"
        assert context.response.status_code == 200
