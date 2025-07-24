# Defines the core TransactionContext for request processing.

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, TypeVar

from httpx import Request, Response

T = TypeVar("T")


@dataclass
class TransactionContext:
    """Holds the state for a single transaction through the proxy.

    Attributes:
        transaction_id: A unique identifier for the transaction.
        request: The incoming HTTP request object.
        response: The outgoing HTTP response object.
        data: A general-purpose dictionary for policies to store and share
            information related to this transaction.
    """

    # Core Identifiers and State
    transaction_id: uuid.UUID = field(default_factory=uuid.uuid4)
    request: Optional[Request] = None
    response: Optional[Response] = None

    # General purpose data store for policies to share information
    data: Dict[str, Any] = field(default_factory=dict)


def get_tx_value(transaction_context: TransactionContext, path: str) -> Any:
    """Get a value from the transaction context using a path.

    Args:
        transaction_context: The transaction context.
        path: The path to the value e.g. "request.headers.user-agent", "response.status_code", "data.user_id".

    Returns:
        The value at the path.

    Raises:
        ValueError: If the path is invalid or the value cannot be accessed.
        TypeError: If the transaction_id is not a UUID.
    """
    vals = path.split(".")
    if len(vals) < 2:
        raise ValueError("Path must contain at least two components")

    x: Any = getattr(transaction_context, vals.pop(0))
    while vals:
        # If x is bytes, and we still have path segments to process,
        # it implies these segments are keys into the JSON content.
        if isinstance(x, bytes) and vals:  # Check if vals is not empty
            x = json.loads(x)

        if isinstance(x, dict):
            x = x[vals.pop(0)]
        else:
            x = getattr(x, vals.pop(0))
    return x
