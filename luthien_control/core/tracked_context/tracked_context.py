"""TrackedContext with explicit mutation API and event tracking."""

import uuid
from copy import copy
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

import httpx

from ..generic_events import Event

httpx_resomething = Union[httpx.Request, httpx.Response]


def _update_headers(
    request: httpx_resomething, headers: Dict[str, str], preserve_existing_headers: bool
) -> dict[str, Any]:
    """Update the request headers. Returns a dict of differences."""
    differences = {
        k: {"old": request.headers.get(k), "new": v} for k, v in headers.items() if request.headers.get(k) != v
    }
    if preserve_existing_headers:
        for k, v in headers.items():
            request.headers[k] = v
    else:
        request.headers = httpx.Headers(headers)
    return differences


@dataclass
class MutationEventPayload:
    """Record of an explicit mutation."""

    transaction_id: Optional[uuid.UUID]
    operation: str  # e.g., "set_header", "set_response_status"
    details: Dict[str, Any]


class ContextEvents:
    mutation: Event[MutationEventPayload] = Event[MutationEventPayload]("context_mutation")


class TrackedContext:
    """Transaction context with explicit mutation API and event tracking."""

    def __init__(self, transaction_id: Optional[uuid.UUID] = None):
        """Initialize tracked context."""
        self._transaction_id = transaction_id or uuid.uuid4()
        self._request: Optional[httpx.Request] = None
        self._response: Optional[httpx.Response] = None
        self._data: Dict[str, Any] = {}
        self.events = ContextEvents()

    @property
    def transaction_id(self) -> uuid.UUID:
        """Get transaction ID."""
        return self._transaction_id

    def update_request(
        self,
        method: Optional[str] = None,
        url: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        content: Optional[bytes] = None,
        from_scratch: bool = False,
        preserve_existing_headers: bool = True,
    ) -> httpx.Request:
        """Create or set the request."""
        differences = {}
        if from_scratch or self._request is None:
            if not all([method, url]):
                raise ValueError("Attempted to create new request, but method and url are required")
            method = str(method)
            url = str(url)
            self._request = httpx.Request(method=method, url=url, headers=headers, content=content)
            differences = {
                k: {"old": None, "new": getattr(self._request, k)} for k in ["method", "url", "headers", "content"]
            }
        else:
            if method is not None:
                differences["method"] = {"old": self._request.method, "new": method}
                self._request.method = method
            if url is not None:
                differences["url"] = {"old": self._request.url, "new": url}
                self._request.url = httpx.URL(url)
            if headers is not None:
                header_diffs = _update_headers(self._request, headers, preserve_existing_headers)
                differences["headers"] = header_diffs
            if content is not None:
                differences["content"] = {"old": self._request.content, "new": content}
                self._request._content = content

        self.events.mutation.dispatch(
            MutationEventPayload(
                transaction_id=self._transaction_id,
                operation="set_request",
                details=differences,
            )
        )
        return self._request

    @property
    def request(self) -> Optional[httpx.Request]:
        """Get a copy of the tracked request."""
        return copy(self._request)

    def update_response(
        self,
        status_code: Optional[int] = None,
        content: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
        from_scratch: bool = False,
        preserve_existing_headers: bool = True,
    ) -> httpx.Response:
        """Update the response."""
        differences = {}
        if from_scratch or self._response is None:
            if not status_code:
                raise ValueError("Attempted to create new response, but status_code is required")
            status_code = int(status_code)
            self._response = httpx.Response(
                status_code=status_code,
                headers=headers,
                content=content,
            )
            differences = {
                k: {"old": None, "new": getattr(self._response, k)} for k in ["status_code", "headers", "content"]
            }
        else:
            if status_code is not None:
                differences["status_code"] = {"old": self._response.status_code, "new": status_code}
                self._response.status_code = status_code
            if headers is not None:
                differences["headers"] = _update_headers(self._response, headers, preserve_existing_headers)
            if content is not None:
                differences["content"] = {"old": self._response.content, "new": content}
                self._response._content = content

        self.events.mutation.dispatch(
            MutationEventPayload(
                transaction_id=self._transaction_id,
                operation="set_response",
                details=differences,
            )
        )
        return self._response

    @property
    def response(self) -> Optional[httpx.Response]:
        """Get a copy of the tracked response."""
        return copy(self._response)

    def get_data(self, key: str, default: Any = None) -> Any:
        """Get data value."""
        return self._data.get(key, default)

    def set_data(self, key: str, value: Any) -> None:
        """Set data value."""
        old_value = self._data.get(key)
        self._data[key] = value
        self.events.mutation.dispatch(
            MutationEventPayload(
                transaction_id=self._transaction_id,
                operation="set_data",
                details={"key": key, "old_value": old_value, "new_value": value},
            )
        )

    def get_all_data(self) -> Dict[str, Any]:
        """Get copy of all data."""
        return self._data.copy()
