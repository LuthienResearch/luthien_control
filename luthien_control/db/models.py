from datetime import datetime, timezone
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field, Json


class ApiKey(BaseModel):
    id: int  # Primary key, usually auto-incrementing
    key_value: str = Field(..., json_schema_extra={"index": True, "unique": True})  # The actual API key string
    name: str = Field(..., json_schema_extra={"index": True})  # A user-friendly name for the key
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata_: Json[Dict[str, Any]] | None = Field(
        default=None
    )  # Using 'metadata_' to avoid potential SQL keyword clash

    model_config = ConfigDict(from_attributes=True)
