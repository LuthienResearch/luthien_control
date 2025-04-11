from datetime import datetime, timezone
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field, Json


class ClientApiKey(BaseModel):
    id: int  # Primary key, usually auto-incrementing
    key_value: str = Field(..., json_schema_extra={"index": True, "unique": True})  # The actual API key string
    name: str = Field(..., json_schema_extra={"index": True})  # A user-friendly name for the key
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata_: Json[Dict[str, Any]] | None = Field(
        default=None
    )  # Using 'metadata_' to avoid potential SQL keyword clash

    model_config = ConfigDict(from_attributes=True)


class Policy(BaseModel):
    name: str = Field(..., json_schema_extra={"index": True, "unique": True})
    policy_class_path: str
    config: Dict[str, Any] | None = None
    is_active: bool = Field(default=True)
    description: str | None = None
    id: int | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = ConfigDict(from_attributes=True)


# Mapping from Pydantic models to database table names
TABLE_NAME_MAP = {
    ClientApiKey: "client_api_keys",
    Policy: "policies",
}
