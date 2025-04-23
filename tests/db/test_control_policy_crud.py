import pytest
from luthien_control.db.control_policy_crud import (
    get_policy_by_name,
    list_policies,
    save_policy_to_db,
    update_policy,
)
from luthien_control.db.sqlmodel_models import ControlPolicy
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

# Mark all tests as async
pytestmark = pytest.mark.asyncio


async def test_create_and_get_policy(async_session: AsyncSession):
    """Test creating and retrieving a policy."""
    # Create a test policy
    policy = ControlPolicy(
        name="test-policy",
        config={"setting": "value"},
        is_active=True,
        description="Test policy description",
        type="mock_type",
    )

    # Create the policy
    created_policy = await save_policy_to_db(async_session, policy)
    assert created_policy is not None
    assert created_policy.id is not None
    assert created_policy.type == "mock_type"

    # Retrieve the policy by name
    retrieved_policy = await get_policy_by_name(async_session, "test-policy")
    assert retrieved_policy is not None
    assert retrieved_policy.id == created_policy.id
    assert retrieved_policy.config == {"setting": "value"}


async def test_list_policies(async_session: AsyncSession):
    """Test listing policies with filtering."""
    # Create multiple policies
    policies = [
        ControlPolicy(name="policy1", is_active=True, type="mock_type"),
        ControlPolicy(name="policy2", is_active=True, type="mock_type"),
        ControlPolicy(name="policy3", is_active=False, type="mock_type"),
    ]

    for policy in policies:
        await save_policy_to_db(async_session, policy)

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
    policy = ControlPolicy(name="update-policy", is_active=True, type="mock_type")
    created_policy = await save_policy_to_db(async_session, policy)
    assert created_policy.id is not None  # Ensure ID is assigned

    # Update the policy
    # Pass a Policy model instance for the update payload
    update_payload = ControlPolicy(
        name="update-policy",  # Not strictly needed by update func
        config={"updated": True},
        description="Updated description",
        is_active=False,  # Example change
    )

    updated_policy = await update_policy(async_session, created_policy.id, update_payload)
    assert updated_policy is not None
    assert updated_policy.config == {"updated": True}
    assert updated_policy.description == "Updated description"
    assert updated_policy.is_active is False

    # Verify the update persisted
    retrieved_policy = await get_policy_by_name(async_session, "update-policy")
    assert retrieved_policy is None


async def test_update_policy_not_found(async_session: AsyncSession):
    """Test updating a non-existent policy."""
    # Pass a Policy model instance
    update_payload = ControlPolicy(description="Updated description")
    updated_policy = await update_policy(async_session, 9999, update_payload)  # Non-existent ID
    assert updated_policy is None


async def test_get_policy_by_name_not_found(async_session: AsyncSession):
    """Test getting a non-existent policy by name."""
    retrieved_policy = await get_policy_by_name(async_session, "non-existent-policy")
    assert retrieved_policy is None


async def test_create_policy_duplicate_name(async_session: AsyncSession):
    """Test creating a policy with a name that already exists."""
    policy1 = ControlPolicy(name="duplicate-name", type="mock_type")
    created_policy1 = await save_policy_to_db(async_session, policy1)
    assert created_policy1 is not None  # Ensure first creation succeeded

    policy2 = ControlPolicy(name="duplicate-name")
    # Expecting IntegrityError because the function now re-raises it
    with pytest.raises(IntegrityError):
        await save_policy_to_db(async_session, policy2)
