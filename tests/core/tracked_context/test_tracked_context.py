"""Tests for TrackedContext."""

import uuid
from unittest.mock import Mock

from luthien_control.core.events import EventBus
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

    def test_event_bus(self):
        """Test that event_bus is an EventBus instance."""
        context = TrackedContext()

        assert isinstance(context.event_bus, EventBus)

    def test_set_current_policy(self):
        """Test setting current policy."""
        context = TrackedContext()

        context.set_current_policy("TestPolicy")
        # Should not raise - internal state tracking

    def test_add_listener(self):
        """Test adding event listeners."""
        context = TrackedContext()
        listener = Mock()

        context.add_listener("TrackedContext.set_data", listener)
        # Should not raise - internal state tracking

    def test_set_request(self):
        """Test setting request."""
        context = TrackedContext()

        request = context.set_request(
            method="POST",
            url="https://api.test.com",
            headers={"Content-Type": "application/json"},
            content=b'{"test": true}',
        )

        assert context.request is request
        assert request.method == "POST"
        assert request.url == "https://api.test.com"

    def test_set_response(self):
        """Test setting response."""
        context = TrackedContext()

        response = context.set_response(
            status_code=200, headers={"Content-Type": "application/json"}, content=b'{"success": true}'
        )

        assert context.response is response
        assert response.status_code == 200

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
        """Test that events are emitted to listeners via EventBus."""
        context = TrackedContext()
        listener = Mock()
        context.add_listener("TrackedContext.set_data", listener)
        context.set_current_policy("TestPolicy")

        # Set data should emit event
        context.set_data("test_key", "test_value")

        # Listener should be called via EventBus
        listener.assert_called_once()
        event = listener.call_args[0][0]
        assert event.name == "TrackedContext.set_data"
        assert event.payload["policy_name"] == "TestPolicy"
        assert event.payload["operation"] == "set_data"
        assert event.payload["details"]["key"] == "test_key"
