from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Column, String
from sqlmodel import Field, SQLModel

# SQLModel models combining SQLAlchemy and Pydantic


# TODO: utcnow() to .now(timezone.utc)
class ClientApiKey(SQLModel, table=True):
    __tablename__ = "client_api_keys"

    id: Optional[int] = Field(default=None, primary_key=True)
    key_value: str = Field(sa_column=Column(String, unique=True, index=True))
    name: str = Field(sa_column=Column(String, index=True))
    is_active: bool = Field(default=True)
    created_at: datetime = Field(
        # Generate naive UTC timestamp to match TIMESTAMP WITHOUT TIME ZONE column
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    # JSON column must be defined explicitly with SQLAlchemy Column
    metadata_: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))


class ControlPolicy(SQLModel, table=True):
    __tablename__ = "policies"
    """Database model for storing control policy configurations."""

    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)

    # --- Core Fields ---
    name: str = Field(index=True, unique=True)  # Unique name used for lookup
    type: str = Field()  # Type of policy, used for instantiation
    config: dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    is_active: bool = Field(default=True, index=True)
    description: Optional[str] = Field(default=None)

    # --- Timestamps ---
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    updated_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

    def __init__(self, **data: Any):
        # Ensure timestamps are set on creation if not provided
        if "created_at" not in data:
            data["created_at"] = datetime.utcnow()
        if "updated_at" not in data:
            data["updated_at"] = datetime.utcnow()
        super().__init__(**data)

    @classmethod
    def get_validators(cls):
        yield cls.validate_timestamps

    @classmethod
    def validate_timestamps(cls, values):
        """Ensure updated_at is always set/updated."""
        values["updated_at"] = datetime.utcnow()
        return values
