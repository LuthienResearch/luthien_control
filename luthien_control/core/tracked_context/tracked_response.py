"""TrackedResponse with explicit mutation API."""

import json
from typing import Any, Callable, Dict, Optional

from .mutation_event import MutationEvent


class TrackedResponse:
    """Response with explicit mutation API."""

    def __init__(
        self, status_code: int, headers: Dict[str, str], content: bytes, emit_fn: Callable[[MutationEvent], None]
    ):
        """Initialize tracked response."""
        self._status_code = status_code
        self._headers = headers.copy()
        self._content = content
        self._emit = emit_fn

    @property
    def status_code(self) -> int:
        """Get status code."""
        return self._status_code

    def set_status_code(self, value: int) -> None:
        """Set status code."""
        old_value = self._status_code
        self._status_code = value
        self._emit(
            MutationEvent(
                transaction_id=None,
                policy_name="",
                operation="set_status_code",
                details={"old_value": old_value, "new_value": value},
            )
        )

    def get_header(self, key: str) -> Optional[str]:
        """Get a header value."""
        return self._headers.get(key)

    def get_headers(self) -> Dict[str, str]:
        """Get copy of all headers."""
        return self._headers.copy()

    @property
    def content(self) -> bytes:
        """Get response content."""
        return self._content

    def get_json(self) -> Any:
        """Parse content as JSON."""
        return json.loads(self._content)

    def set_header(self, key: str, value: str) -> None:
        """Set a header value."""
        old_value = self._headers.get(key)
        self._headers[key] = value
        self._emit(
            MutationEvent(
                transaction_id=None,
                policy_name="",
                operation="set_header",
                details={"key": key, "old_value": old_value, "new_value": value},
            )
        )

    def remove_header(self, key: str) -> None:
        """Remove a header."""
        if key in self._headers:
            old_value = self._headers[key]
            del self._headers[key]
            self._emit(
                MutationEvent(
                    transaction_id=None,
                    policy_name="",
                    operation="remove_header",
                    details={"key": key, "old_value": old_value},
                )
            )

    def set_json_content(self, data: Any) -> None:
        """Set content from JSON data."""
        self._content = json.dumps(data).encode("utf-8")
        self._emit(
            MutationEvent(
                transaction_id=None,
                policy_name="",
                operation="set_json_content",
                details={"content_length": len(self._content)},
            )
        )
