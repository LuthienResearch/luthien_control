from typing import Any, ClassVar

from psygnal import EventedModel, Signal


class DeepEventedModel(EventedModel):
    """A Pydantic EventedModel that emits a single `changed` signal on any change.

    This includes changes to top-level fields as well as changes within
    nested evented containers (like EventedList, EventedDict) or other
    DeepEventedModel instances.

    Attributes:
        changed: A signal that is emitted with no arguments when any value
                 in the model or its nested evented children changes.
    """

    changed: ClassVar[Signal] = Signal()

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        # Connect our master `changed` signal to the base model's event group.
        # This handles all top-level field assignments.
        self.events.connect(self.changed)
        # Connect to the event groups of any initial child objects.
        self._connect_children()

    def __setattr__(self, name: str, value: Any) -> None:
        # Before the attribute is set, we must disconnect from the old child object.
        if name in self.__class__.model_fields:
            old_value = getattr(self, name, None)
            self._disconnect_child(old_value)

        super().__setattr__(name, value)

        # After the attribute is set, we connect to the new child object.
        if name in self.__class__.model_fields:
            new_value = getattr(self, name)
            self._connect_child(new_value)
            # The base EventedModel handles emitting the field-specific signal,
            # which is already piped to our `changed` signal.

    def _connect_child(self, child: Any) -> None:
        """If `child` is an evented object, connect its events to our signal."""
        if self._is_evented(child):
            child.events.connect(self.changed)

    def _disconnect_child(self, child: Any) -> None:
        """If `child` is an evented object, disconnect its events."""
        if self._is_evented(child):
            try:
                child.events.disconnect(self.changed)
            except (TypeError, ValueError):
                pass  # It's okay if it was never connected

    def _connect_children(self) -> None:
        """Connect to the events of all evented children in the model."""
        for name in self.__class__.model_fields:
            child = getattr(self, name)
            self._connect_child(child)

    def _is_evented(self, obj: Any) -> bool:
        """Check if an object has a connectable `events` signal group."""
        events = getattr(obj, "events", None)
        return events is not None and callable(getattr(events, "connect", None))
