"""Utilities for working with TrackedContext."""

import json
from typing import Any

from .tracked_context import TrackedContext


def get_tx_value(tracked_context: TrackedContext, path: str) -> Any:
    """Get a value from the tracked context using a path.

    Args:
        tracked_context: The tracked context.
        path: The path to the value e.g. "request.headers.user-agent", "response.status_code", "data.user_id".

    Returns:
        The value at the path.

    Raises:
        ValueError: If the path is invalid or the value cannot be accessed.
    """
    vals = path.split(".")
    if len(vals) < 2:
        raise ValueError("Path must contain at least two components")

    # Handle the first segment specially for TrackedContext
    first_segment = vals.pop(0)
    if first_segment == "request":
        if tracked_context.request is None:
            raise ValueError("Request is None in tracked context")
        x: Any = tracked_context.request
    elif first_segment == "response":
        if tracked_context.response is None:
            raise ValueError("Response is None in tracked context")
        x = tracked_context.response
    elif first_segment == "data":
        x = tracked_context.get_all_data()
    else:
        raise ValueError(f"Invalid path segment: {first_segment}")

    while vals:
        next_segment = vals.pop(0)

        if hasattr(x, "content") and next_segment == "content":
            x = x.content
            # If we have more path segments and content is bytes, try to parse as JSON
            if vals and isinstance(x, bytes):
                try:
                    x = json.loads(x)
                except json.JSONDecodeError as e:
                    raise ValueError(
                        f"Failed to decode JSON content for path '{path}' at segment '{next_segment}'"
                    ) from e
            continue
        """
        # Handle TrackedRequest/TrackedResponse special properties
        if hasattr(x, "get_header") and next_segment == "headers":
            x = x.get_headers()
            continue
        elif hasattr(x, "get_json") and next_segment == "json":
            x = x.get_json()
            continue
        elif hasattr(x, "status_code") and next_segment == "status_code":
            x = x.status_code
            continue
        elif hasattr(x, "method") and next_segment == "method":
            x = x.method
            continue
        elif hasattr(x, "url") and next_segment == "url":
            x = x.url
            continue
        """

        # If x is bytes, and we still have path segments to process,
        # it implies these segments are keys into the JSON content.
        if isinstance(x, bytes) and vals:  # Check if vals is not empty
            try:
                x = json.loads(x)
            except json.JSONDecodeError as e:
                # Wrapping the original error for better diagnostics
                raise ValueError(f"Failed to decode JSON content for path '{path}' at segment '{next_segment}'") from e

        if isinstance(x, dict):
            x = x[next_segment]
        else:
            x = getattr(x, next_segment)
    return x
