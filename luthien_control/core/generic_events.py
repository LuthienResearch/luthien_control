"""Generic event system with type-safe event dispatching."""

import logging
from typing import Callable, Dict, Generic, TypeVar

T = TypeVar("T")


type EventListener[T] = Callable[[str, T], None]


class Event(Generic[T]):
    """A generic event that maintains a named registry of typed event listeners to be dispatched on demand.


    Typical usage:
        start_policy_event = LuthienEventType("start_policy")
        event: Event[dict] = Event[dict](start_policy_event)
        data = {"foo": "bar"}
        def listener_1(event_type, data):
            print(f"Listener 1 received event: {event_type} {data}")
        def listener_2(event_type, data):
            print(f"Listener 2 received event: {event_type} {data}")

        event.register("listener_1", listener_1)
        event.register("listener_2", listener_2)
        event.dispatch(data)  # Listener 1 and 2 will receive the event
        event.unregister("listener_1")
        event.dispatch(data)  # Listener 2 will receive the event

    Type Parameters:
        T: The type of data that will be passed to event listeners
    """

    def __init__(self, event_type: str) -> None:
        """Initialize an event with no registered listeners.

        Args:
            event_type: The type of event this observer is for
        """
        self._event_type = event_type
        self._listeners: Dict[str, EventListener[T]] = {}

    def register(self, name: str, listener: EventListener[T]) -> None:
        """Register a named observer.

        Args:
            name: Unique identifier for this listener
            listener: Callable that accepts an argument of type T
        """
        self._listeners[name] = listener

    def unregister(self, name: str) -> None:
        """Remove a registered observer by name.

        Args:
            name: The name of the listener to remove

        Raises:
            KeyError: If no listener with the given name exists
        """
        del self._listeners[name]

    def dispatch(self, data: T) -> None:
        """Dispatch the event to all registered observers.

        Args:
            data: The data of type T to pass to all listeners
        """
        for name, listener in self._listeners.items():
            try:
                listener(self._event_type, data)
            except Exception as e:
                logging.exception(f"Error dispatching event to listener {name}: {e}")

    @property
    def listener_count(self) -> int:
        """Return the number of registered listeners."""
        return len(self._listeners)

    def get_listeners(self) -> Dict[str, EventListener[T]]:
        """Return a *copy* of the registered listeners dictionary.

        Returns:
            A copy of the listeners registry
        """
        return self._listeners.copy()
