from datetime import datetime, timezone

import pytest
from luthien_control.db.api_key_crud import get_api_key_by_value
from luthien_control.db.sqlmodel_crud import (
    create_api_key,
    create_policy,
    get_policy_by_name,
    list_api_keys,
    list_policies,
    update_api_key,
    update_policy,
)
from luthien_control.db.sqlmodel_models import ClientApiKey, Policy
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
    created_key = await create_api_key(async_session, api_key)
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

    updated_key = await update_api_key(async_session, created_key.id, update_payload)
    assert updated_key is not None
    assert updated_key.name == "Updated Name"
    assert updated_key.metadata_ == {"updated": True}

    # Verify the update persisted
    retrieved_key = await get_api_key_by_value(async_session, "update-key")
    assert retrieved_key is not None
    assert retrieved_key.name == "Updated Name"
    assert retrieved_key.metadata_ == {"updated": True}


async def test_update_api_key_not_found(async_session: AsyncSession):
    """Test updating a non-existent API key."""
    # Pass a ClientApiKey model instance
    update_payload = ClientApiKey(name="Updated Name")
    updated_key = await update_api_key(async_session, 9999, update_payload)  # Non-existent ID
    assert updated_key is None


async def test_get_api_key_by_value_not_found(async_session: AsyncSession):
    """Test getting a non-existent API key by value."""
    retrieved_key = await get_api_key_by_value(async_session, "non-existent-key")
    assert retrieved_key is None


async def test_create_and_get_policy(async_session: AsyncSession):
    """Test creating and retrieving a policy."""
    # Create a test policy
    policy = Policy(
        name="test-policy",
        policy_class_path="luthien_control.policies.test.TestPolicy",
        config={"setting": "value"},
        is_active=True,
        description="Test policy description",
    )

    # Create the policy
    created_policy = await create_policy(async_session, policy)
    assert created_policy is not None
    assert created_policy.id is not None
    assert created_policy.name == "test-policy"

    # Retrieve the policy by name
    retrieved_policy = await get_policy_by_name(async_session, "test-policy")
    assert retrieved_policy is not None
    assert retrieved_policy.id == created_policy.id
    assert retrieved_policy.policy_class_path == "luthien_control.policies.test.TestPolicy"
    assert retrieved_policy.config == {"setting": "value"}


async def test_list_policies(async_session: AsyncSession):
    """Test listing policies with filtering."""
    # Create multiple policies
    policies = [
        Policy(name="policy1", policy_class_path="path1", is_active=True),
        Policy(name="policy2", policy_class_path="path2", is_active=True),
        Policy(name="policy3", policy_class_path="path3", is_active=False),
    ]

    for policy in policies:
        await create_policy(async_session, policy)

    # List all policies
    all_policies = await list_policies(async_session)
    assert len(all_policies) == 3

    # List only active policies
    active_policies = await list_policies(async_session, active_only=True)
    assert len(active_policies) == 2
    assert all(policy.is_active for policy in active_policies)


async def test_update_policy(async_session: AsyncSession):
    """Test updating a policy."""
    # Create a policy
    policy = Policy(name="update-policy", policy_class_path="original.path", is_active=True)
    created_policy = await create_policy(async_session, policy)
    assert created_policy.policy_class_path == "original.path"
    assert created_policy.id is not None  # Ensure ID is assigned

    # Update the policy
    # Pass a Policy model instance for the update payload
    update_payload = Policy(
        name="update-policy",  # Not strictly needed by update func
        policy_class_path="updated.path",
        config={"updated": True},
        description="Updated description",
        is_active=False,  # Example change
    )

    updated_policy = await update_policy(async_session, created_policy.id, update_payload)
    assert updated_policy is not None
    assert updated_policy.policy_class_path == "updated.path"
    assert updated_policy.config == {"updated": True}
    assert updated_policy.description == "Updated description"
    assert updated_policy.is_active is False

    # Verify the update persisted
    retrieved_policy = await get_policy_by_name(async_session, "update-policy")
    assert retrieved_policy is None


async def test_update_policy_not_found(async_session: AsyncSession):
    """Test updating a non-existent policy."""
    # Pass a Policy model instance
    update_payload = Policy(description="Updated description")
    updated_policy = await update_policy(async_session, 9999, update_payload)  # Non-existent ID
    assert updated_policy is None


async def test_get_policy_by_name_not_found(async_session: AsyncSession):
    """Test getting a non-existent policy by name."""
    retrieved_policy = await get_policy_by_name(async_session, "non-existent-policy")
    assert retrieved_policy is None


async def test_create_policy_duplicate_name(async_session: AsyncSession):
    """Test creating a policy with a name that already exists."""
    policy1 = Policy(name="duplicate-name", policy_class_path="path1")
    created_policy1 = await create_policy(async_session, policy1)
    assert created_policy1 is not None  # Ensure first creation succeeded

    policy2 = Policy(name="duplicate-name", policy_class_path="path2")
    # Expecting None because the function catches the IntegrityError and returns None
    created_policy2 = await create_policy(async_session, policy2)
    assert created_policy2 is None
