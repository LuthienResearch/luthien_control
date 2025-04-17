from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg  # Import for exception testing
import pytest
from luthien_control.db.models import Policy
from luthien_control.db.policy_crud import create_policy_config, update_policy_config

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_db_pool():
    """Fixture to provide a mock database pool and connection."""
    mock_conn = AsyncMock()
    mock_pool = MagicMock()
    # Make the pool context manager return the mock connection
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    return mock_pool, mock_conn


@pytest.fixture
def sample_policy_data() -> Policy:
    """Provides a sample Policy object for testing creation."""
    return Policy(
        name="test_policy_create",
        policy_class_path="luthien_control.policies.AllowAll",
        config={"setting": "value"},
        is_active=True,
        description="A test policy for creation",
        # id, created_at, updated_at are ignored/set by DB
    )


@pytest.fixture
def sample_db_record() -> dict:
    """Provides a sample dictionary representing a fetched DB record."""
    now = datetime.now(timezone.utc)
    return {
        "id": 123,
        "name": "test_policy_create",
        "policy_class_path": "luthien_control.policies.AllowAll",
        "config": {"setting": "value"},  # Assume DB returns dict or JSON parsed by fetchrow mock
        "is_active": True,
        "description": "A test policy for creation",
        "created_at": now,
        "updated_at": now,
    }


async def test_create_policy_config_success(mock_db_pool, sample_policy_data, sample_db_record):
    """Tests successful creation of a policy configuration."""
    mock_pool, mock_conn = mock_db_pool

    # Mock fetchrow to return the newly created record simulation
    mock_conn.fetchrow.return_value = sample_db_record

    # Patch get_main_db_pool to return our mock pool
    with patch("luthien_control.db.policy_crud.get_main_db_pool", return_value=mock_pool):
        created_policy = await create_policy_config(sample_policy_data)

    # Assertions
    assert created_policy is not None
    assert created_policy.id == sample_db_record["id"]
    assert created_policy.name == sample_policy_data.name
    assert created_policy.policy_class_path == sample_policy_data.policy_class_path
    assert created_policy.config == sample_policy_data.config
    assert created_policy.is_active == sample_policy_data.is_active
    assert created_policy.description == sample_policy_data.description
    assert created_policy.created_at is not None
    assert created_policy.updated_at is not None

    # Check if fetchrow was called correctly (assuming INSERT...RETURNING)
    mock_conn.fetchrow.assert_awaited_once()
    # More detailed check of the SQL and args passed to fetchrow will be needed
    # once the actual implementation is written.


async def test_create_policy_config_db_pool_not_initialized(sample_policy_data):
    """Tests behavior when the database pool is not initialized."""
    # Patch get_main_db_pool to raise RuntimeError
    with patch("luthien_control.db.policy_crud.get_main_db_pool", side_effect=RuntimeError("Pool not init")):
        created_policy = await create_policy_config(sample_policy_data)

    assert created_policy is None


async def test_create_policy_config_db_error_on_insert(mock_db_pool, sample_policy_data):
    """Tests behavior when the database fetchrow raises an exception."""
    mock_pool, mock_conn = mock_db_pool

    # Configure fetchrow to raise a generic Exception
    mock_conn.fetchrow.side_effect = Exception("DB connection error")

    # Patch get_main_db_pool
    with patch("luthien_control.db.policy_crud.get_main_db_pool", return_value=mock_pool):
        created_policy = await create_policy_config(sample_policy_data)

    assert created_policy is None
    mock_conn.fetchrow.assert_awaited_once()


# Potential additional tests:
# - Test for unique constraint violation (e.g., duplicate name)
# - Test for validation error if the returned record is somehow invalid (less likely for CREATE)
# - Test with different input variations (e.g., null config, null description)


# --- Tests for update_policy_config ---


@pytest.fixture
def policy_update_payload(sample_policy_data) -> Policy:
    """Provides a Policy object with modified data for update testing."""
    # Create a copy and modify fields
    updated_data = sample_policy_data.model_copy(deep=True)
    updated_data.description = "Updated description for test policy"
    updated_data.is_active = False
    updated_data.config = {"new_setting": "new_value"}
    # Keep name and class path the same for standard update tests
    return updated_data


@pytest.fixture
def updated_db_record(sample_db_record, policy_update_payload) -> dict:
    """Provides a sample DB record dict reflecting the updated data."""
    # Simulate the DB record *after* the update
    record = sample_db_record.copy()
    record["description"] = policy_update_payload.description
    record["is_active"] = policy_update_payload.is_active
    record["config"] = policy_update_payload.config
    record["updated_at"] = datetime.now(timezone.utc)  # Simulate DB setting new timestamp
    # ID and created_at remain the same
    return record


async def test_update_policy_config_success(mock_db_pool, policy_update_payload, updated_db_record):
    """Tests successful update of a policy configuration."""
    mock_pool, mock_conn = mock_db_pool
    policy_id_to_update = 123  # Use the ID from sample_db_record fixture

    # Mock fetchrow to return the *updated* record simulation
    mock_conn.fetchrow.return_value = updated_db_record

    with patch("luthien_control.db.policy_crud.get_main_db_pool", return_value=mock_pool):
        updated_policy = await update_policy_config(policy_id_to_update, policy_update_payload)

    # Assertions
    assert updated_policy is not None
    assert updated_policy.id == policy_id_to_update
    assert updated_policy.name == policy_update_payload.name  # Should remain the same
    assert updated_policy.policy_class_path == policy_update_payload.policy_class_path
    # Check updated fields
    assert updated_policy.config == policy_update_payload.config
    assert updated_policy.is_active == policy_update_payload.is_active
    assert updated_policy.description == policy_update_payload.description
    assert updated_policy.created_at == updated_db_record["created_at"]  # Should not change
    assert updated_policy.updated_at == updated_db_record["updated_at"]  # Should be new

    # Check DB call
    mock_conn.fetchrow.assert_awaited_once()
    # We could add more specific checks on the SQL and args if needed


async def test_update_policy_config_not_found(mock_db_pool, policy_update_payload):
    """Tests update when the policy ID is not found."""
    mock_pool, mock_conn = mock_db_pool
    non_existent_id = 999

    # Mock fetchrow to return None (simulating record not found)
    mock_conn.fetchrow.return_value = None

    with patch("luthien_control.db.policy_crud.get_main_db_pool", return_value=mock_pool):
        result = await update_policy_config(non_existent_id, policy_update_payload)

    assert result is None
    mock_conn.fetchrow.assert_awaited_once()


async def test_update_policy_config_db_error(mock_db_pool, policy_update_payload):
    """Tests update when the database call raises an exception."""
    mock_pool, mock_conn = mock_db_pool
    policy_id_to_update = 123

    # Mock fetchrow to raise an error
    mock_conn.fetchrow.side_effect = Exception("DB update error")

    with patch("luthien_control.db.policy_crud.get_main_db_pool", return_value=mock_pool):
        result = await update_policy_config(policy_id_to_update, policy_update_payload)

    assert result is None
    mock_conn.fetchrow.assert_awaited_once()


async def test_update_policy_config_unique_violation(mock_db_pool, policy_update_payload):
    """Tests update failure due to unique constraint (e.g., conflicting name update)."""
    mock_pool, mock_conn = mock_db_pool
    policy_id_to_update = 123

    # Mock fetchrow to raise UniqueViolationError
    mock_conn.fetchrow.side_effect = asyncpg.UniqueViolationError("duplicate key value violates unique constraint")

    with patch("luthien_control.db.policy_crud.get_main_db_pool", return_value=mock_pool):
        result = await update_policy_config(policy_id_to_update, policy_update_payload)

    assert result is None
    mock_conn.fetchrow.assert_awaited_once()


# Potential additional tests:
# - Test behavior when _parse_and_validate_policy_record returns None after update
