"""Defines the core TransactionContext for request processing."""

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Union

import httpx
from fastapi import Response as FastAPIResponse

# Type alias for potential response types set by policies
PolicyResponseType = Union[FastAPIResponse, httpx.Response, None]


@dataclass
class TransactionContext:
    """Holds the state for a single transaction through the proxy."""

    # Core Identifiers and State
    transaction_id: uuid.UUID = field(default_factory=uuid.uuid4)
    request: Optional[httpx.Request] = None
    response: Optional[httpx.Response] = None

    # General purpose data store for policies to share information
    data: Dict[str, Any] = field(default_factory=dict)
