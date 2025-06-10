"""TrackedContext with explicit mutation API and event tracking."""

import uuid
from typing import Any, Dict, Optional

from ..events import EventBus
from .mutation_event import MutationEvent
from .tracked_request import TrackedRequest
from .tracked_response import TrackedResponse


class TrackedContext:
    """Transaction context with explicit mutation API and event tracking."""

    def __init__(self, transaction_id: Optional[uuid.UUID] = None):
        """Initialize tracked context."""
        self._transaction_id = transaction_id or uuid.uuid4()
        self._request: Optional[TrackedRequest] = None
        self._response: Optional[TrackedResponse] = None
        self._data: Dict[str, Any] = {}
        self._current_policy: Optional[str] = None
        self.event_bus = EventBus()

    @property
    def transaction_id(self) -> uuid.UUID:
        """Get transaction ID."""
        return self._transaction_id

    def set_current_policy(self, policy_name: Optional[str]) -> None:
        """Set the current policy making changes."""
        self._current_policy = policy_name

    def add_listener(self, event_name: str, listener) -> None:
        """Add an event listener for a specific event."""
        self.event_bus.add_listener(event_name, listener)

    def _emit(self, event: MutationEvent) -> None:
        """Emit an event to all listeners."""
        # Fill in context information
        event.transaction_id = self._transaction_id
        event.policy_name = self._current_policy or "unknown"

        # Dispatch via EventBus
        self.event_bus.dispatch(
            event_name=f"TrackedContext.{event.operation}",
            payload={
                "transaction_id": str(event.transaction_id),
                "policy_name": event.policy_name,
                "operation": event.operation,
                "details": event.details,
            },
        )

    def set_request(self, method: str, url: str, headers: Dict[str, str], content: bytes) -> TrackedRequest:
        """Create and set the request."""
        self._request = TrackedRequest(method, url, headers, content, self._emit)
        self._emit(
            MutationEvent(
                transaction_id=self._transaction_id,
                policy_name=self._current_policy or "unknown",
                operation="set_request",
                details={"method": method, "url": url},
            )
        )
        return self._request

    @property
    def request(self) -> Optional[TrackedRequest]:
        """Get the tracked request."""
        return self._request

    def set_response(self, status_code: int, headers: Dict[str, str], content: bytes) -> TrackedResponse:
        """Create and set the response."""
        self._response = TrackedResponse(status_code, headers, content, self._emit)
        self._emit(
            MutationEvent(
                transaction_id=self._transaction_id,
                policy_name=self._current_policy or "unknown",
                operation="set_response",
                details={"status_code": status_code},
            )
        )
        return self._response

    @property
    def response(self) -> Optional[TrackedResponse]:
        """Get the tracked response."""
        return self._response

    def get_data(self, key: str, default: Any = None) -> Any:
        """Get data value."""
        return self._data.get(key, default)

    def set_data(self, key: str, value: Any) -> None:
        """Set data value."""
        old_value = self._data.get(key)
        self._data[key] = value
        self._emit(
            MutationEvent(
                transaction_id=self._transaction_id,
                policy_name=self._current_policy or "unknown",
                operation="set_data",
                details={"key": key, "old_value": old_value, "new_value": value},
            )
        )

    def get_all_data(self) -> Dict[str, Any]:
        """Get copy of all data."""
        return self._data.copy()
