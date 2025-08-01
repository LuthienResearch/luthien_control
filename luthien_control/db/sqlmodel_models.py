import datetime as dt
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import model_validator
from sqlalchemy import JSON, Column, DateTime, Index, String, types
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func
from sqlmodel import Field, SQLModel

from .naive_datetime import NaiveDatetime

# SQLModel models combining SQLAlchemy and Pydantic


class JsonBOrJson(types.TypeDecorator):
    """
    Represents a JSON type that uses JSONB for PostgreSQL and JSON for other dialects (like SQLite).

    This is mostly a hack for unit testing, as SQLite does not support JSONB.
    """

    impl = JSON  # Default implementation if dialect-specific is not found
    cache_ok = True  # Safe to cache this type decorator

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        else:
            return dialect.type_descriptor(JSON())


class ClientApiKey(SQLModel, table=True):
    __tablename__ = "client_api_keys"  # type: ignore (shut up pyright)

    id: Optional[int] = Field(default=None, primary_key=True)
    key_value: str = Field(sa_column=Column(String, unique=True, index=True))
    name: str = Field(sa_column=Column(String, index=True))
    is_active: bool = Field(default=True)
    created_at: dt.datetime = Field(
        # Generate naive UTC timestamp to match TIMESTAMP WITHOUT TIME ZONE column
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    # JSON column must be defined explicitly with SQLAlchemy Column
    metadata_: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))


class ControlPolicy(SQLModel, table=True):
    __tablename__ = "policies"  # type: ignore (again, shut up pyright)
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
    created_at: dt.datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )
    updated_at: dt.datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=False
    )

    def __init__(self, **data: Any):
        # Ensure timestamps are set on creation if not provided
        if "created_at" not in data:
            data["created_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
        if "updated_at" not in data:
            data["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
        super().__init__(**data)

    @model_validator(mode="before")
    @classmethod
    def validate_timestamps(cls, values):
        """Ensure updated_at is always set/updated."""
        if isinstance(values, dict):
            values["updated_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
        return values


class LuthienLog(SQLModel, table=True):
    """
    Represents a log entry in the Luthien logging system using SQLModel.

    Attributes:
        id: Unique identifier for the log entry (primary key).
        transaction_id: Identifier to group related log entries.
        datetime: Timestamp indicating when the log entry was generated (timezone-aware).
        data: JSON blob containing the primary logged data.
        datatype: String identifier for the nature and schema of 'data'.
        notes: JSON blob for additional contextual information.
    """

    __tablename__ = "luthien_log"  # type: ignore (shut up pyright)

    id: Optional[int] = Field(default=None, primary_key=True, index=True)
    transaction_id: str = Field(index=True, nullable=False)
    datetime: NaiveDatetime = Field(
        default_factory=NaiveDatetime.now,
        nullable=False,
        index=True,
    )
    data: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JsonBOrJson))
    datatype: str = Field(index=True, nullable=False)
    notes: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JsonBOrJson))

    def __init__(self, **data: Any) -> None:
        """Override init to ensure datetime is converted to NaiveDatetime."""
        if "datetime" in data:
            dt_value = data["datetime"]
            if isinstance(dt_value, datetime) and not isinstance(dt_value, NaiveDatetime):
                data["datetime"] = NaiveDatetime(dt_value)
        super().__init__(**data)

    # __table_args__ = (
    #     Index("ix_sqlmodel_luthien_log_transaction_id", "transaction_id"),
    #     Index("ix_sqlmodel_luthien_log_datetime", "datetime"),
    #     Index("ix_sqlmodel_luthien_log_datatype", "datatype"),
    #     {"extend_existing": True},
    # )

    # __repr__ is not automatically generated by SQLModel like Pydantic models,
    # but you can add one if desired.
    def __repr__(self) -> str:
        return (
            f"<LuthienLog(id={self.id}, "
            f"transaction_id='{self.transaction_id}', "
            f"datetime='{self.datetime}', "
            f"datatype='{self.datatype}')>"
        )


class AdminUser(SQLModel, table=True):
    """Admin user model for authentication and authorization."""

    __tablename__ = "admin_users"  # type: ignore

    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(sa_column=Column(String(50), unique=True, nullable=False))
    password_hash: str = Field(sa_column=Column(String(255), nullable=False))
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    last_login: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now()),
    )

    __table_args__ = (
        Index("idx_admin_username", "username"),
        Index("idx_admin_active", "is_active"),
    )


class AdminSession(SQLModel, table=True):
    """Admin session model for managing active sessions."""

    __tablename__ = "admin_sessions"  # type: ignore

    id: Optional[int] = Field(default=None, primary_key=True)
    session_token: str = Field(sa_column=Column(String(255), unique=True, nullable=False))
    admin_user_id: int = Field(
        foreign_key="admin_users.id",
        description="Reference to admin user",
    )
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    __table_args__ = (
        Index("idx_session_token", "session_token"),
        Index("idx_session_expires", "expires_at"),
    )
