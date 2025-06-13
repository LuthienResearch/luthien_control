import logging
from unittest.mock import MagicMock, patch

import pytest
from luthien_control.core.generic_events import Event


class TestGenericEvent:
    """Unit tests for the generic `Event` helper."""

    def test_register_and_dispatch(self):
        """Registering listeners and dispatching should call each listener with event type and data."""
        event_type = "test_event"
        payload = {"foo": "bar"}
        event: Event[dict] = Event(event_type)

        listener_one = MagicMock()
        listener_two = MagicMock()

        event.register("listener_one", listener_one)
        event.register("listener_two", listener_two)

        # Ensure listeners are counted correctly
        assert event.listener_count == 2

        # Dispatch the payload
        event.dispatch(payload)

        listener_one.assert_called_once_with(event_type, payload)
        listener_two.assert_called_once_with(event_type, payload)

        # get_listeners should return a copy – mutating it must not affect the original
        listeners_snapshot = event.get_listeners()
        listeners_snapshot.pop("listener_one")
        assert event.listener_count == 2, "Modifying the snapshot should not influence the original registry"

    def test_unregister(self):
        """Unregister removes a listener and raises KeyError for unknown names."""
        event: Event[int] = Event("int_event")
        listener = MagicMock()
        event.register("my_listener", listener)

        event.unregister("my_listener")
        assert event.listener_count == 0

        # Dispatching after unregister should not call the listener
        event.dispatch(123)
        listener.assert_not_called()

        # Attempting to unregister again should raise KeyError
        with pytest.raises(KeyError):
            event.unregister("non_existent")

    def test_dispatch_with_exception_in_listener(self):
        """Exceptions raised by listeners must be caught and logged; other listeners continue to run."""
        event: Event[str] = Event("fault_tolerant")

        def faulty_listener(evt_type: str, data: str):  # noqa: ANN001 – test helper
            raise ValueError("Boom!")

        good_listener = MagicMock()

        event.register("bad", faulty_listener)
        event.register("good", good_listener)

        with patch.object(logging, "exception") as mock_log_exc:
            event.dispatch("payload")

            # The good listener should still be called despite the failure of the first one
            good_listener.assert_called_once_with("fault_tolerant", "payload")

            # The exception from the faulty listener must be logged via logging.exception
            mock_log_exc.assert_called_once()
