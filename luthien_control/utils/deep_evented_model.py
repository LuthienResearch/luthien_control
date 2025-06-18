from typing import Any, ClassVar

from psygnal import EventedModel, Signal
from psygnal.containers import EventedDict, EventedList
from pydantic import ConfigDict, model_serializer


class DeepEventedModel(EventedModel):
    """A Pydantic EventedModel that emits a single `changed` signal on any change.

    This includes changes to top-level fields as well as changes within
    nested evented containers (like EventedList, EventedDict) or other
    DeepEventedModel instances.

    Attributes:
        changed: A signal that is emitted with no arguments when any value
                 in the model or its nested evented children changes.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)
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
        if isinstance(child, DeepEventedModel):
            child.changed.connect(self.changed)
        elif isinstance(child, EventedList):
            child.events.connect(self.changed)
            child.events.inserted.connect(self._on_item_inserted)
            child.events.removed.connect(self._on_item_removed)
            for item in child:
                self._connect_child(item)
        elif isinstance(child, EventedDict):
            child.events.connect(self.changed)
            child.events.added.connect(self._on_item_added)
            for item in child.values():
                self._connect_child(item)
        elif self._is_evented(child):
            child.events.connect(self.changed)

    def _disconnect_child(self, child: Any) -> None:
        """If `child` is an evented object, disconnect its events."""
        if isinstance(child, DeepEventedModel):
            child.changed.disconnect(self.changed)
        elif isinstance(child, EventedList):
            child.events.disconnect(self.changed)
            child.events.inserted.disconnect(self._on_item_inserted)
            child.events.removed.disconnect(self._on_item_removed)
            for item in child:
                self._disconnect_child(item)
        elif isinstance(child, EventedDict):
            child.events.disconnect(self.changed)
            child.events.added.disconnect(self._on_item_added)
            for item in child.values():
                self._disconnect_child(item)
        elif self._is_evented(child):
            child.events.disconnect(self.changed)

    def _on_item_inserted(self, index: int, value: Any):
        self._connect_child(value)

    def _on_item_removed(self, index: int, value: Any):
        self._disconnect_child(value)

    def _on_item_added(self, key: str, value: Any):
        self._connect_child(value)

    def _connect_children(self) -> None:
        """Connect to the events of all evented children in the model."""
        for name in self.__class__.model_fields:
            child = getattr(self, name)
            self._connect_child(child)

    def _is_evented(self, obj: Any) -> bool:
        """Check if an object has a connectable `events` signal group."""
        events = getattr(obj, "events", None)
        return events is not None and callable(getattr(events, "connect", None))

    @model_serializer(mode="wrap")
    def _serialize_model(self, serializer, info):
        """Custom model serializer that converts EventedList and EventedDict to regular containers."""
        # First, check if this model actually has any EventedList or EventedDict fields
        has_evented_containers = False
        for field_name, field_info in self.__class__.model_fields.items():
            value = getattr(self, field_name)
            if isinstance(value, (EventedList, EventedDict)):
                has_evented_containers = True
                break

        # If no evented containers, use default serialization
        if not has_evented_containers:
            return serializer(self)

        # Otherwise, handle evented containers specially
        data = {}
        for field_name, field_info in self.__class__.model_fields.items():
            value = getattr(self, field_name)
            if isinstance(value, EventedList):
                data[field_name] = list(value)
            elif isinstance(value, EventedDict):
                data[field_name] = dict(value)
            else:
                # For other types, use the default field serialization
                data[field_name] = value
        return data
