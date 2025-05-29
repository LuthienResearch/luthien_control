from datetime import datetime, timezone
from typing import cast
from unittest.mock import Mock

import pytest
from luthien_control.db.client_api_key_crud import (
    create_api_key,
    get_api_key_by_value,
    list_api_keys,
    update_api_key,
)
from luthien_control.db.exceptions import (
    LuthienDBIntegrityError,
    LuthienDBOperationError,
    LuthienDBQueryError,
    LuthienDBTransactionError,
)
from luthien_control.db.sqlmodel_models import ClientApiKey
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

# Test database fixtures (async_engine, async_session) are now expected
# to be provided by tests/db/conftest.py

# Mark all tests as async
pytestmark = pytest.mark.asyncio


async def test_create_and_get_api_key(async_session: AsyncSession):
    """Test creating and retrieving an API key."""
    # Create a test API key
    api_key = ClientApiKey(
        key_value="test-key-123",
        name="Test API Key",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        metadata_={"purpose": "testing"},
    )

    # Create the API key
    created_key = await create_api_key(async_session, api_key)
    assert created_key is not None
    assert created_key.id is not None
    assert created_key.key_value == "test-key-123"

    # Retrieve the API key by value
    retrieved_key = await get_api_key_by_value(async_session, "test-key-123")
    assert retrieved_key is not None
    assert retrieved_key.id == created_key.id
    assert retrieved_key.name == "Test API Key"
    assert retrieved_key.metadata_ == {"purpose": "testing"}


async def test_list_api_keys(async_session: AsyncSession):
    """Test listing API keys with filtering."""
    # Create multiple API keys
    keys = [
        ClientApiKey(key_value="key1", name="Active Key 1", is_active=True),
        ClientApiKey(key_value="key2", name="Active Key 2", is_active=True),
        ClientApiKey(key_value="key3", name="Inactive Key", is_active=False),
    ]

    for key in keys:
        await create_api_key(async_session, key)

    # List all keys
    all_keys = await list_api_keys(async_session)
    assert len(all_keys) == 3

    # List only active keys
    active_keys = await list_api_keys(async_session, active_only=True)
    assert len(active_keys) == 2
    assert all(key.is_active for key in active_keys)


async def test_update_api_key(async_session: AsyncSession):
    """Test updating an API key."""
    # Create an API key
    api_key = ClientApiKey(key_value="update-key", name="Original Name", is_active=True)
    created_key_val = await create_api_key(async_session, api_key)
    assert created_key_val is not None
    created_key = cast(ClientApiKey, created_key_val)
    assert created_key.name == "Original Name"
    assert created_key.id is not None  # Ensure ID is assigned

    # Update the API key
    # Pass a ClientApiKey model instance for the update payload
    update_payload = ClientApiKey(
        key_value="update-key",  # Not strictly needed by update func, but good practice
        name="Updated Name",
        is_active=True,
        metadata_={"updated": True},
    )

    updated_key_val = await update_api_key(async_session, created_key.id, update_payload)
    assert updated_key_val is not None
    updated_key = cast(ClientApiKey, updated_key_val)
    assert updated_key.id is not None  # Explicitly assert id is not None
    assert updated_key.name == "Updated Name"
    assert updated_key.metadata_ == {"updated": True}

    # Verify the update persisted
    retrieved_key_val = await get_api_key_by_value(async_session, "update-key")
    assert retrieved_key_val is not None
    retrieved_key = cast(ClientApiKey, retrieved_key_val)
    assert retrieved_key.id is not None  # Explicitly assert id is not None
    assert retrieved_key.name == "Updated Name"
    assert retrieved_key.metadata_ == {"updated": True}


async def test_update_api_key_not_found(async_session: AsyncSession):
    """Test updating a non-existent API key."""
    # Pass a ClientApiKey model instance
    # Add a dummy key_value as it's required by the model
    update_payload = ClientApiKey(key_value="dummy-key-for-non-existent", name="Updated Name")
    updated_key = await update_api_key(async_session, 9999, update_payload)  # Non-existent ID
    assert updated_key is None


async def test_get_api_key_by_value_not_found(async_session: AsyncSession):
    """Test getting a non-existent API key by value."""
    retrieved_key = await get_api_key_by_value(async_session, "non-existent-key")
    assert retrieved_key is None


async def test_get_api_key_by_value_invalid_session():
    """Test getting an API key with invalid session object."""
    # Create a mock that's not an AsyncSession
    invalid_session = Mock()

    with pytest.raises(TypeError):
        await get_api_key_by_value(invalid_session, "test-key")


async def test_get_api_key_by_value_exception(async_session: AsyncSession, monkeypatch):
    """Test exception handling in get_api_key_by_value."""

    # Mock the session.execute to raise an exception
    async def mock_execute(*args, **kwargs):
        raise Exception("Database error")

    monkeypatch.setattr(async_session, "execute", mock_execute)

    # Function should raise LuthienDBOperationError
    with pytest.raises(LuthienDBOperationError, match="Unexpected error during API key lookup"):
        await get_api_key_by_value(async_session, "test-key")


async def test_create_api_key_exception(async_session: AsyncSession, monkeypatch):
    """Test exception handling in create_api_key."""

    # Mock session.commit to raise an exception
    async def mock_commit(*args, **kwargs):
        raise Exception("Database error")

    monkeypatch.setattr(async_session, "commit", mock_commit)

    api_key = ClientApiKey(key_value="error-key", name="Error Key")
    with pytest.raises(LuthienDBOperationError, match="Unexpected error during API key creation"):
        await create_api_key(async_session, api_key)


async def test_list_api_keys_exception(async_session: AsyncSession, monkeypatch):
    """Test exception handling in list_api_keys."""

    # Mock session.execute to raise an exception
    async def mock_execute(*args, **kwargs):
        raise Exception("Database error")

    monkeypatch.setattr(async_session, "execute", mock_execute)

    # Function should raise LuthienDBOperationError
    with pytest.raises(LuthienDBOperationError, match="Unexpected error during API key listing"):
        await list_api_keys(async_session)


async def test_update_api_key_exception(async_session: AsyncSession, monkeypatch):
    """Test exception handling in update_api_key."""
    # Create a key first
    api_key = ClientApiKey(key_value="update-exception-key", name="Original Name")
    created_key = await create_api_key(async_session, api_key)
    assert created_key is not None
    assert created_key.id is not None

    # Mock session.commit to raise an exception
    async def mock_commit(*args, **kwargs):
        raise Exception("Database error")

    monkeypatch.setattr(async_session, "commit", mock_commit)

    update_payload = ClientApiKey(key_value="update-exception-key", name="Updated Name")
    with pytest.raises(LuthienDBOperationError, match="Unexpected error during API key update"):
        await update_api_key(async_session, created_key.id, update_payload)


async def test_get_api_key_by_value_sqlalchemy_error(async_session: AsyncSession, monkeypatch):
    """Test SQLAlchemyError handling in get_api_key_by_value."""

    # Mock the session.execute to raise a SQLAlchemyError
    async def mock_execute(*args, **kwargs):
        raise SQLAlchemyError("SQLAlchemy database error")

    monkeypatch.setattr(async_session, "execute", mock_execute)

    # Function should raise LuthienDBQueryError
    with pytest.raises(LuthienDBQueryError, match="Database query failed while fetching API key"):
        await get_api_key_by_value(async_session, "test-key")


async def test_create_api_key_integrity_error(async_session: AsyncSession, monkeypatch):
    """Test IntegrityError handling in create_api_key."""

    # Mock session.commit to raise an IntegrityError
    async def mock_commit(*args, **kwargs):
        raise IntegrityError("statement", "params", "orig")

    monkeypatch.setattr(async_session, "commit", mock_commit)

    api_key = ClientApiKey(key_value="integrity-error-key", name="Integrity Error Key")
    with pytest.raises(LuthienDBIntegrityError, match="Could not create API key due to constraint violation"):
        await create_api_key(async_session, api_key)


async def test_create_api_key_sqlalchemy_error(async_session: AsyncSession, monkeypatch):
    """Test SQLAlchemyError handling in create_api_key."""

    # Mock session.commit to raise a SQLAlchemyError
    async def mock_commit(*args, **kwargs):
        raise SQLAlchemyError("SQLAlchemy database error")

    monkeypatch.setattr(async_session, "commit", mock_commit)

    api_key = ClientApiKey(key_value="sqlalchemy-error-key", name="SQLAlchemy Error Key")
    with pytest.raises(LuthienDBTransactionError, match="Database transaction failed while creating API key"):
        await create_api_key(async_session, api_key)


async def test_list_api_keys_sqlalchemy_error(async_session: AsyncSession, monkeypatch):
    """Test SQLAlchemyError handling in list_api_keys."""

    # Mock session.execute to raise a SQLAlchemyError
    async def mock_execute(*args, **kwargs):
        raise SQLAlchemyError("SQLAlchemy database error")

    monkeypatch.setattr(async_session, "execute", mock_execute)

    # Function should raise LuthienDBQueryError
    with pytest.raises(LuthienDBQueryError, match="Database query failed while listing API keys"):
        await list_api_keys(async_session)


async def test_update_api_key_integrity_error(async_session: AsyncSession, monkeypatch):
    """Test IntegrityError handling in update_api_key."""
    # Create a key first
    api_key = ClientApiKey(key_value="update-integrity-error-key", name="Original Name")
    created_key = await create_api_key(async_session, api_key)
    assert created_key is not None
    assert created_key.id is not None

    # Mock session.commit to raise an IntegrityError
    async def mock_commit(*args, **kwargs):
        raise IntegrityError("statement", "params", "orig")

    monkeypatch.setattr(async_session, "commit", mock_commit)

    update_payload = ClientApiKey(key_value="update-integrity-error-key", name="Updated Name")
    with pytest.raises(LuthienDBIntegrityError, match="Could not update API key due to constraint violation"):
        await update_api_key(async_session, created_key.id, update_payload)


async def test_update_api_key_sqlalchemy_error(async_session: AsyncSession, monkeypatch):
    """Test SQLAlchemyError handling in update_api_key."""
    # Create a key first
    api_key = ClientApiKey(key_value="update-sqlalchemy-error-key", name="Original Name")
    created_key = await create_api_key(async_session, api_key)
    assert created_key is not None
    assert created_key.id is not None

    # Mock session.commit to raise a SQLAlchemyError
    async def mock_commit(*args, **kwargs):
        raise SQLAlchemyError("SQLAlchemy database error")

    monkeypatch.setattr(async_session, "commit", mock_commit)

    update_payload = ClientApiKey(key_value="update-sqlalchemy-error-key", name="Updated Name")
    with pytest.raises(LuthienDBTransactionError, match="Database transaction failed while updating API key"):
        await update_api_key(async_session, created_key.id, update_payload)
