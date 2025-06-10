"""Core components for a generic, in-transaction event system."""

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, MutableMapping


@dataclass
class Event:
    """Represents a generic event that has occurred.

    Attributes:
        name: The name of the event (e.g., "Policy.Decision").
        payload: A dictionary containing data about the event.
    """

    name: str
    payload: Dict[str, Any] = field(default_factory=dict)


# An EventListener is a function that takes an Event and does something.
# It can be any callable that conforms to this signature.
EventListener = Callable[[Event], None]


class EventBus:
    """A simple event bus for a single transaction.

    This class manages a collection of listeners and dispatches events to them.
    It's designed to be instantiated once per transaction and live on the
    TransactionContext.
    """

    def __init__(self) -> None:
        """Initializes the EventBus."""
        self._listeners: MutableMapping[str, List[EventListener]] = {}

    def add_listener(self, event_name: str, listener: EventListener) -> None:
        """Registers a listener for a specific event name.

        Args:
            event_name: The name of the event to listen for.
            listener: The callable function to execute when the event is dispatched.
        """
        if event_name not in self._listeners:
            self._listeners[event_name] = []
        self._listeners[event_name].append(listener)

    def dispatch(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Creates an Event and dispatches it to all registered listeners.

        Args:
            event_name: The name of the event to dispatch.
            payload: The data payload for the event.
        """
        event = Event(name=event_name, payload=payload)
        if event.name in self._listeners:
            for listener in self._listeners[event.name]:
                try:
                    # Listeners are called synchronously.
                    listener(event)
                except Exception:
                    # TODO: Inject a logger to handle listener exceptions.
                    # For now, ensure one failing listener doesn't stop others.
                    pass
