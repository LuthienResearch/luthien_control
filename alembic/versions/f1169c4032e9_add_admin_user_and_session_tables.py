"""add admin user and session tables

Revision ID: f1169c4032e9
Revises: 50deccdf11ab
Create Date: 2025-07-21 12:22:18.783636

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1169c4032e9"
down_revision: Union[str, None] = "50deccdf11ab"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create admin_users table
    op.create_table(
        "admin_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("idx_admin_username", "admin_users", ["username"], unique=False)
    op.create_index("idx_admin_active", "admin_users", ["is_active"], unique=False)

    # Create admin_sessions table
    op.create_table(
        "admin_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_token", sa.String(length=255), nullable=False),
        sa.Column("admin_user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["admin_user_id"],
            ["admin_users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_token"),
    )
    op.create_index("idx_session_token", "admin_sessions", ["session_token"], unique=False)
    op.create_index("idx_session_expires", "admin_sessions", ["expires_at"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_session_expires", table_name="admin_sessions")
    op.drop_index("idx_session_token", table_name="admin_sessions")
    op.drop_table("admin_sessions")
    op.drop_index("idx_admin_active", table_name="admin_users")
    op.drop_index("idx_admin_username", table_name="admin_users")
    op.drop_table("admin_users")
