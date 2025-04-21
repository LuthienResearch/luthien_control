"""Defines the core TransactionContext for request processing."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import httpx


@dataclass
class TransactionContext:
    """Carries state throughout the request processing flow."""

    transaction_id: str
    request: Optional[httpx.Request] = None
    response: Optional[httpx.Response] = None
    data: Dict[Any, Any] = field(default_factory=dict)
