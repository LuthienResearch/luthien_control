"""TrackedRequest with explicit mutation API."""

import json
from typing import Any, Callable, Dict, Optional

from .mutation_event import MutationEvent


class TrackedRequest:
    """Request with explicit mutation API."""

    def __init__(
        self, method: str, url: str, headers: Dict[str, str], content: bytes, emit_fn: Callable[[MutationEvent], None]
    ):
        """Initialize tracked request."""
        self._method = method
        self._url = url
        self._headers = headers.copy()
        self._content = content
        self._emit = emit_fn

    @property
    def method(self) -> str:
        """Get HTTP method."""
        return self._method

    @property
    def url(self) -> str:
        """Get URL as string."""
        return self._url

    def get_header(self, key: str) -> Optional[str]:
        """Get a header value."""
        return self._headers.get(key)

    def get_headers(self) -> Dict[str, str]:
        """Get copy of all headers."""
        return self._headers.copy()

    @property
    def content(self) -> bytes:
        """Get request content."""
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
                transaction_id=None,  # Will be set by context
                policy_name="",  # Will be set by context
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
