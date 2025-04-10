from datetime import datetime
from typing import Any, Dict

from pydantic import BaseModel, Field, Json


class ApiKey(BaseModel):
    id: int  # Primary key, usually auto-incrementing
    key_value: str = Field(..., index=True, unique=True)  # The actual API key string
    name: str = Field(..., index=True)  # A user-friendly name for the key
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata_: Json[Dict[str, Any]] | None = Field(
        default=None
    )  # Using 'metadata_' to avoid potential SQL keyword clash

    class Config:
        orm_mode = True  # To allow mapping from ORM objects if we use one later
