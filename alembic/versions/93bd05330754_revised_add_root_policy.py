"""Add root CompoundPolicy

Revision ID: 93bd05330754_revised
Revises: e19a50fe197b
Create Date: 2025-04-18 17:55:16.262055

"""

import json
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# Import postgresql dialect for ON CONFLICT DO UPDATE
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "93bd05330754_revised"
down_revision: Union[str, None] = "e19a50fe197b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# --- Configuration for the root policy ---
ROOT_POLICY_NAME = "root"
ROOT_POLICY_TYPE = "CompoundPolicy"
# NOTE: For direct insertion via SQLAlchemy Core, we pass the dict directly
ROOT_POLICY_CONFIG = {
    "policies": [
        {"type": "ClientApiKeyAuth", "config": {"name": "ClientAPIKeyCheck"}},
        {"type": "AddApiKeyHeader", "config": {"name": "AddBackendKey"}},
        {"type": "SendBackendRequest", "config": {"name": "ForwardRequest"}},
    ]
}
ROOT_POLICY_DESCRIPTION = "Root policy configuration defining the core request flow"
# --- End Configuration ---


def upgrade() -> None:
    """Insert or update the root policy configuration using SQLAlchemy Core."""
    bind = op.get_bind()
    # Define the table structure minimally for the operation
    policies_table = sa.Table(
        "policies",
        sa.MetaData(),
        sa.Column("name", sa.String, primary_key=True),
        sa.Column("type", sa.String, nullable=False),
        sa.Column("config", sa.JSON, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    now_utc = datetime.now(timezone.utc)

    # Prepare the values for insertion
    values = {
        "name": ROOT_POLICY_NAME,
        "type": ROOT_POLICY_TYPE,
        "config": ROOT_POLICY_CONFIG,  # Pass dict directly, driver handles JSON
        "is_active": True,
        "description": ROOT_POLICY_DESCRIPTION,
        "created_at": now_utc,
        "updated_at": now_utc,
    }

    # Use PostgreSQL's INSERT ... ON CONFLICT DO UPDATE
    insert_stmt = postgresql.insert(policies_table).values(values)

    update_stmt = insert_stmt.on_conflict_do_update(
        index_elements=["name"],  # Constraint to check
        set_={  # Columns to update on conflict
            "type": insert_stmt.excluded.type,
            "config": insert_stmt.excluded.config,
            "is_active": insert_stmt.excluded.is_active,
            "description": insert_stmt.excluded.description,
            "updated_at": insert_stmt.excluded.updated_at,
        },
    )

    # Execute the statement
    bind.execute(update_stmt)


def downgrade() -> None:
    """Remove the root policy configuration using parameterized query."""
    bind = op.get_bind()
    policies_table = sa.Table(
        "policies",
        sa.MetaData(),
        sa.Column("name", sa.String, primary_key=True),
        sa.Column("type", sa.String),
        sa.Column("config", sa.JSON),
    )

    # Use SQLAlchemy Core expression language for safety
    delete_stmt = sa.delete(policies_table).where(
        sa.and_(
            policies_table.c.name == sa.bindparam("name"),
            policies_table.c.type == sa.bindparam("type"),
            # JSON comparison needs care; direct equality check might work
            # depending on DB/driver, but comparing the serialized form is safer
            # if we expect an exact match of the config *as defined here*.
            # However, since we upserted, just deleting by name is likely sufficient
            # and avoids potential JSON comparison pitfalls.
            # policies_table.c.config == sa.bindparam('config', type_=sa.JSON) # Less reliable
        )
    )

    # Execute the delete statement with parameters
    # Simpler downgrade: Just delete by name, assuming we "own" the root policy.
    simple_delete_stmt = sa.delete(policies_table).where(policies_table.c.name == sa.bindparam("name"))

    bind.execute(simple_delete_stmt, {"name": ROOT_POLICY_NAME})

    # If strict matching (like original downgrade) is needed:
    # bind.execute(delete_stmt, {
    #     "name": ROOT_POLICY_NAME,
    #     "type": ROOT_POLICY_TYPE,
    #     # "config": ROOT_POLICY_CONFIG # Passing dict might work for bindparam with JSON type
    # })
