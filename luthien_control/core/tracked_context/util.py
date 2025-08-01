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

    for next_segment in vals:
        if isinstance(x, bytes):
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
