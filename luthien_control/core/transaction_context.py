# Defines the core TransactionContext for request processing.

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import httpx


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
    request: Optional[httpx.Request] = None
    response: Optional[httpx.Response] = None

    # General purpose data store for policies to share information
    data: Dict[str, Any] = field(default_factory=dict)
