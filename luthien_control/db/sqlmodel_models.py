from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import JSON, Column, String
from sqlmodel import Field, SQLModel


# SQLModel models combining SQLAlchemy and Pydantic
class ClientApiKey(SQLModel, table=True):
    __tablename__ = "client_api_keys"

    id: Optional[int] = Field(default=None, primary_key=True)
    key_value: str = Field(sa_column=Column(String, unique=True, index=True))
    name: str = Field(sa_column=Column(String, index=True))
    is_active: bool = Field(default=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    # JSON column must be defined explicitly with SQLAlchemy Column
    metadata_: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON)
    )


class Policy(SQLModel, table=True):
    __tablename__ = "policies"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String, unique=True, index=True))
    policy_class_path: str = Field(sa_column=Column(String))
    # JSON column must be defined explicitly with SQLAlchemy Column
    config: Optional[Dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON)
    )
    is_active: bool = Field(default=True)
    description: Optional[str] = Field(default=None, sa_column=Column(String, nullable=True))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
