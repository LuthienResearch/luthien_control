"""MutationEvent dataclass for tracking context changes."""

import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class MutationEvent:
    """Record of an explicit mutation."""

    transaction_id: Optional[uuid.UUID]
    policy_name: str
    operation: str  # e.g., "set_header", "set_response_status"
    details: Dict[str, Any]
