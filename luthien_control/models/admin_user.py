"""Admin user model for authentication."""

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Index, String
from sqlalchemy.sql import func
from sqlmodel import Field, SQLModel


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
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
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
        default_factory=datetime.utcnow,
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    __table_args__ = (
        Index("idx_session_token", "session_token"),
        Index("idx_session_expires", "expires_at"),
    )
