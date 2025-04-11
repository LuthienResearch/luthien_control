import datetime
import json
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import httpx
import pytest
from luthien_control.config.settings import Settings

# Import the actual policy loader parts needed for patching/exceptions
from luthien_control.core.policy_loader import ApiKeyLookupFunc

# Import only what's needed for CRUD tests
from luthien_control.db.crud import (
    PolicyLoadError,
    get_api_key_by_value,
    get_policy_config_by_name,
    load_policy_from_db,
)
from luthien_control.db.models import ApiKey, Policy

# Mark all tests in this module as async
pytestmark = pytest.mark.asyncio


@pytest.fixture
def mock_db_pool():
    """Fixture to mock the database pool and connection."""
    mock_conn = AsyncMock(spec=asyncpg.Connection)
    mock_pool = MagicMock(spec=asyncpg.Pool)
    # Configure the pool's acquire method to return an async context manager
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_pool.acquire.return_value.__aexit__.return_value = None  # Simulate successful exit
    return mock_pool, mock_conn


async def test_get_api_key_by_value_found_active(mock_db_pool):
    """Test fetching an existing, active API key."""
    mock_pool, mock_conn = mock_db_pool
    test_key = "test-key-active"
    now = datetime.datetime.now(datetime.UTC)
    mock_metadata_dict = {"user": "test"}
    mock_metadata_str = json.dumps(mock_metadata_dict)

    # Simulate fetchrow returning a dictionary matching the ApiKey model structure
    mock_record_dict = {
        "id": 1,
        "key_value": test_key,
        "name": "Test Key Active",
        "is_active": True,
        "created_at": now,
        "metadata_": mock_metadata_str,  # DB returns JSON as string
    }
    # asyncpg returns a Record object, but we mock fetchrow to return the dict
    # This simplifies testing the Pydantic model creation
    mock_conn.fetchrow.return_value = mock_record_dict

    # Patch get_main_db_pool to return our mock pool
    with patch("luthien_control.db.crud.get_main_db_pool", return_value=mock_pool):
        result = await get_api_key_by_value(test_key)

    assert isinstance(result, ApiKey)
    assert result.key_value == test_key
    assert result.name == "Test Key Active"
    assert result.is_active is True
    assert result.created_at == now
    assert result.metadata_ == mock_metadata_dict  # Check deserialized metadata

    # Assert the SQL query was called correctly, ignoring whitespace differences
    mock_conn.fetchrow.assert_awaited_once()
    call_args = mock_conn.fetchrow.await_args
    actual_query = call_args[0][0]
    actual_param = call_args[0][1]

    expected_query = """
        SELECT id, key_value, name, is_active, created_at, metadata_
        FROM api_keys
        WHERE key_value = $1
    """

    # Normalize whitespace (split by any whitespace, join with single space)
    normalized_actual = " ".join(actual_query.split())
    normalized_expected = " ".join(expected_query.split())

    assert normalized_actual == normalized_expected
    assert actual_param == test_key


async def test_get_api_key_by_value_not_found(mock_db_pool):
    """Test fetching a non-existent API key."""
    mock_pool, mock_conn = mock_db_pool
    test_key = "test-key-nonexistent"

    # Simulate fetchrow returning None (key not found)
    mock_conn.fetchrow.return_value = None

    with patch("luthien_control.db.crud.get_main_db_pool", return_value=mock_pool):
        result = await get_api_key_by_value(test_key)

    assert result is None
    mock_conn.fetchrow.assert_awaited_once()


async def test_get_api_key_by_value_db_error(mock_db_pool):
    """Test behavior when the database query fails."""
    mock_pool, mock_conn = mock_db_pool
    test_key = "test-key-error"

    # Simulate fetchrow raising an exception
    mock_conn.fetchrow.side_effect = asyncpg.PostgresError("Simulated DB error")

    with patch("luthien_control.db.crud.get_main_db_pool", return_value=mock_pool):
        result = await get_api_key_by_value(test_key)

    assert result is None
    mock_conn.fetchrow.assert_awaited_once()


async def test_get_api_key_by_value_pool_not_initialized():
    """Test behavior when the DB pool is not initialized."""
    test_key = "test-key-no-pool"

    # Patch get_main_db_pool to raise RuntimeError
    with patch("luthien_control.db.crud.get_main_db_pool", side_effect=RuntimeError("Pool not initialized")):
        result = await get_api_key_by_value(test_key)

    assert result is None


async def test_get_api_key_by_value_found_inactive(mock_db_pool):
    """Test fetching an existing, but inactive API key (should still return it)."""
    mock_pool, mock_conn = mock_db_pool
    test_key = "test-key-inactive"
    now = datetime.datetime.now(datetime.UTC)

    mock_record_dict = {
        "id": 2,
        "key_value": test_key,
        "name": "Test Key Inactive",
        "is_active": False,
        "created_at": now,
        "metadata_": None,
    }
    mock_conn.fetchrow.return_value = mock_record_dict

    with patch("luthien_control.db.crud.get_main_db_pool", return_value=mock_pool):
        result = await get_api_key_by_value(test_key)

    assert isinstance(result, ApiKey)
    assert result.key_value == test_key
    assert result.is_active is False


async def test_get_api_key_by_value_invalid_metadata_json(mock_db_pool):
    """Test fetching a key where metadata is invalid JSON."""
    mock_pool, mock_conn = mock_db_pool
    test_key = "test-key-bad-json"
    now = datetime.datetime.now(datetime.UTC)
    mock_metadata_str = "this is not valid json"

    mock_record_dict = {
        "id": 3,
        "key_value": test_key,
        "name": "Test Key Bad JSON",
        "is_active": True,
        "created_at": now,
        "metadata_": mock_metadata_str,
    }
    mock_conn.fetchrow.return_value = mock_record_dict

    with patch("luthien_control.db.crud.get_main_db_pool", return_value=mock_pool):
        # Patch logger.warning to check if it's called
        with patch("luthien_control.db.crud.logger.warning") as mock_warning:
            result = await get_api_key_by_value(test_key)

    assert isinstance(result, ApiKey)
    assert result.key_value == test_key
    assert result.metadata_ is None  # Should be set to None due to parsing error
    mock_warning.assert_called_once()
    # Check that the specific warning about invalid JSON was logged
    assert "Invalid JSON in metadata" in mock_warning.call_args[0][0]


async def test_get_api_key_by_value_found(mock_db_pool):
    mock_pool, mock_conn = mock_db_pool
    test_key = "test-value"
    expected_record = {
        "id": 1,
        "key_value": test_key,
        "name": "Test Key",
        "is_active": True,
        "created_at": datetime.datetime.now(datetime.UTC),
        "metadata_": None,
    }
    mock_conn.fetchrow.return_value = expected_record

    with patch("luthien_control.db.crud.get_main_db_pool", return_value=mock_pool):
        result_key = await get_api_key_by_value(test_key)

    assert result_key == ApiKey(**expected_record)  # type: ignore

    # Assert the SQL query was called correctly, ignoring whitespace differences
    mock_conn.fetchrow.assert_awaited_once()
    call_args = mock_conn.fetchrow.await_args
    actual_query = call_args[0][0]
    actual_param = call_args[0][1]

    expected_query = """
        SELECT id, key_value, name, is_active, created_at, metadata_
        FROM api_keys
        WHERE key_value = $1
    """

    # Normalize whitespace (split by any whitespace, join with single space)
    normalized_actual = " ".join(actual_query.split())
    normalized_expected = " ".join(expected_query.split())

    assert normalized_actual == normalized_expected
    assert actual_param == test_key


# --- Tests for get_policy_config_by_name --- #


async def test_get_policy_config_by_name_found_active(mock_db_pool):
    """Test fetching an existing, active policy configuration."""
    mock_pool, mock_conn = mock_db_pool
    test_name = "root_policy"
    now = datetime.datetime.now(datetime.UTC)
    test_config = {"param1": "value1", "timeout": 60}

    # Simulate fetchrow returning a dictionary matching the Policy model structure
    mock_record_dict = {
        "id": 10,
        "name": test_name,
        "policy_class_path": "luthien_control.policies.RootPolicy",
        "config": test_config,  # Assuming DB returns a dict or JSONB compatible
        "is_active": True,
        "description": "The main entry policy",
        "created_at": now,
        "updated_at": now,
    }
    mock_conn.fetchrow.return_value = mock_record_dict

    with patch("luthien_control.db.crud.get_main_db_pool", return_value=mock_pool):
        result = await get_policy_config_by_name(test_name)

    assert isinstance(result, Policy)
    assert result.name == test_name
    assert result.policy_class_path == "luthien_control.policies.RootPolicy"
    assert result.is_active is True
    assert result.config == test_config
    assert result.description == "The main entry policy"
    assert result.id == 10
    assert result.created_at == now
    assert result.updated_at == now

    # Assert the SQL query was called correctly
    mock_conn.fetchrow.assert_awaited_once()
    call_args = mock_conn.fetchrow.await_args
    actual_query = call_args[0][0]
    actual_param = call_args[0][1]

    expected_query = """
        SELECT id, name, policy_class_path, config, is_active, description, created_at, updated_at
        FROM policies
        WHERE name = $1 AND is_active = TRUE
    """
    normalized_actual = " ".join(actual_query.split())
    normalized_expected = " ".join(expected_query.split())

    assert normalized_actual == normalized_expected
    assert actual_param == test_name


async def test_get_policy_config_by_name_not_found(mock_db_pool):
    """Test fetching a non-existent policy name."""
    mock_pool, mock_conn = mock_db_pool
    test_name = "nonexistent_policy"

    mock_conn.fetchrow.return_value = None

    with patch("luthien_control.db.crud.get_main_db_pool", return_value=mock_pool):
        result = await get_policy_config_by_name(test_name)

    assert result is None
    mock_conn.fetchrow.assert_awaited_once()


async def test_get_policy_config_by_name_found_inactive(mock_db_pool):
    """Test fetching a policy that exists but is_active=False (should return None)."""
    mock_pool, mock_conn = mock_db_pool
    test_name = "inactive_policy"

    # The query specifically asks for is_active = TRUE, so fetchrow would return None
    mock_conn.fetchrow.return_value = None

    with patch("luthien_control.db.crud.get_main_db_pool", return_value=mock_pool):
        result = await get_policy_config_by_name(test_name)

    assert result is None
    mock_conn.fetchrow.assert_awaited_once()
    # Verify the query still includes 'is_active = TRUE'
    call_args = mock_conn.fetchrow.await_args
    actual_query = call_args[0][0]
    assert "is_active = TRUE" in actual_query


async def test_get_policy_config_by_name_db_error(mock_db_pool):
    """Test behavior when the database query for policy fails."""
    mock_pool, mock_conn = mock_db_pool
    test_name = "policy_db_error"

    mock_conn.fetchrow.side_effect = asyncpg.PostgresError("Simulated DB error")

    with patch("luthien_control.db.crud.get_main_db_pool", return_value=mock_pool):
        result = await get_policy_config_by_name(test_name)

    assert result is None
    mock_conn.fetchrow.assert_awaited_once()


async def test_get_policy_config_by_name_pool_not_initialized():
    """Test behavior when the DB pool is not initialized for policy fetch."""
    test_name = "policy_no_pool"

    with patch("luthien_control.db.crud.get_main_db_pool", side_effect=RuntimeError("Pool not initialized")):
        result = await get_policy_config_by_name(test_name)

    assert result is None


async def test_get_policy_config_by_name_validation_error(mock_db_pool):
    """Test behavior when DB returns data that fails Pydantic validation."""
    mock_pool, mock_conn = mock_db_pool
    test_name = "policy_bad_data"
    now = datetime.datetime.now(datetime.UTC)

    # Simulate fetchrow returning data with a missing required field (e.g., policy_class_path)
    mock_record_dict = {
        "id": 11,
        "name": test_name,
        # "policy_class_path": "missing.path", # Missing required field
        "config": {},
        "is_active": True,
        "description": "Bad data",
        "created_at": now,
        "updated_at": now,
    }
    mock_conn.fetchrow.return_value = mock_record_dict

    with patch("luthien_control.db.crud.get_main_db_pool", return_value=mock_pool):
        # Patch logger.error to check if it's called
        with patch("luthien_control.db.crud.logger.error") as mock_error:
            result = await get_policy_config_by_name(test_name)

    assert result is None  # Should return None on validation error
    mock_conn.fetchrow.assert_awaited_once()
    mock_error.assert_called_once()
    assert "Pydantic validation failed" in mock_error.call_args[0][0]


# --- Fixtures specifically for load_policy_from_db --- #


@pytest.fixture
def load_db_mock_settings() -> Settings:
    """Provides a mock Settings object specifically for load_from_db tests."""
    return MagicMock(spec=Settings)


@pytest.fixture
def load_db_mock_http_client() -> httpx.AsyncClient:
    """Provides a mock httpx.AsyncClient specifically for load_from_db tests."""
    return MagicMock(spec=httpx.AsyncClient)


@pytest.fixture
def load_db_mock_api_key_lookup() -> ApiKeyLookupFunc:
    """Provides a mock ApiKeyLookupFunc specifically for load_from_db tests."""
    return AsyncMock()


@pytest.fixture
def load_db_dependencies(load_db_mock_settings, load_db_mock_http_client, load_db_mock_api_key_lookup):
    """Bundles the dependencies for load_policy_from_db tests."""
    return {
        "settings": load_db_mock_settings,
        "http_client": load_db_mock_http_client,
        "api_key_lookup": load_db_mock_api_key_lookup,
    }


# Helper to create mock Policy model instances for get_policy_config_by_name patch
def create_mock_policy_model(
    id: int = 1,
    name: str = "test_policy",
    policy_class_path: str = "module.MockSimplePolicy",
    config: dict | None = None,
    is_active: bool = True,
    description: str | None = "A test policy",
    created_at: datetime.datetime | None = None,
    updated_at: datetime.datetime | None = None,
) -> Policy:
    """Creates a mock Policy object for testing."""
    now = datetime.datetime.now(datetime.UTC)
    # Ensure config is a dict if None
    config_dict = config if config is not None else {}
    return Policy(
        id=id,
        name=name,
        policy_class_path=policy_class_path,
        config=config_dict,
        is_active=is_active,
        description=description,
        created_at=created_at or now,
        updated_at=updated_at or now,
    )


# --- Tests for load_policy_from_db --- #


@patch("luthien_control.db.crud.get_policy_config_by_name")
@patch("luthien_control.db.crud.instantiate_policy", new_callable=AsyncMock)
async def test_load_policy_from_db_success(mock_instantiate, mock_get_config, load_db_dependencies):
    """Test successful loading and instantiation via load_policy_from_db."""
    policy_name = "root_policy"
    # Use a valid mock class path to avoid ImportError during test setup
    mock_policy_model = create_mock_policy_model(
        name=policy_name,
        policy_class_path="tests.db.mock_policies.MockSimplePolicy",
        config={"db_param": "db_value", "timeout": 123},  # Add timeout expected by MockSimplePolicy
    )
    mock_get_config.return_value = mock_policy_model

    # Assign return_value to the AsyncMock
    mock_instantiated_policy = MagicMock()
    mock_instantiate.return_value = mock_instantiated_policy

    result = await load_policy_from_db(policy_name, **load_db_dependencies)

    mock_get_config.assert_awaited_once_with(policy_name)

    # Check that instantiate_policy was called with combined config
    expected_initial_config = {
        "db_param": "db_value",
        "timeout": 123,
        "name": policy_name,  # Name from model overrides config
        "policy_class_path": "tests.db.mock_policies.MockSimplePolicy",  # Path from model
    }
    # Use assert_awaited_once_with for AsyncMock
    mock_instantiate.assert_awaited_once_with(
        policy_config=expected_initial_config,
        settings=load_db_dependencies["settings"],
        http_client=load_db_dependencies["http_client"],
        api_key_lookup=load_db_dependencies["api_key_lookup"],
    )

    assert result is mock_instantiated_policy


@patch("luthien_control.db.crud.get_policy_config_by_name", return_value=None)
async def test_load_policy_from_db_not_found(mock_get_config, load_db_dependencies):
    """Test PolicyLoadError if get_policy_config_by_name returns None."""
    policy_name = "not_found_policy"
    with pytest.raises(PolicyLoadError, match=f"Active policy configuration named '{policy_name}' not found"):
        await load_policy_from_db(policy_name, **load_db_dependencies)
    mock_get_config.assert_awaited_once_with(policy_name)


@patch("luthien_control.db.crud.get_policy_config_by_name")
async def test_load_policy_from_db_missing_class_path(mock_get_config, load_db_dependencies):
    """Test PolicyLoadError if the fetched policy model is missing policy_class_path."""
    policy_name = "no_path_policy"
    # Mock the return value directly as a MagicMock to avoid Policy model validation
    mock_policy_model = MagicMock(spec=Policy)
    mock_policy_model.name = policy_name
    mock_policy_model.policy_class_path = None  # Simulate missing path
    mock_policy_model.config = {}

    mock_get_config.return_value = mock_policy_model

    with pytest.raises(PolicyLoadError, match="missing 'policy_class_path'"):
        await load_policy_from_db(policy_name, **load_db_dependencies)
    mock_get_config.assert_awaited_once_with(policy_name)


@patch("luthien_control.db.crud.get_policy_config_by_name")
@patch(
    "luthien_control.db.crud.instantiate_policy",
    new_callable=AsyncMock,
    side_effect=PolicyLoadError("Instantiation failed"),
)
async def test_load_policy_from_db_instantiation_fails(mock_instantiate, mock_get_config, load_db_dependencies):
    """Test that PolicyLoadError from instantiate_policy is propagated."""
    policy_name = "fail_instantiate_policy"
    # Use a valid mock path
    mock_policy_model = create_mock_policy_model(
        name=policy_name, policy_class_path="tests.db.mock_policies.MockSimplePolicy"
    )
    mock_get_config.return_value = mock_policy_model

    # Now the instantiate_policy patch (AsyncMock) should take effect correctly
    with pytest.raises(PolicyLoadError, match="Instantiation failed"):
        await load_policy_from_db(policy_name, **load_db_dependencies)

    mock_get_config.assert_awaited_once_with(policy_name)
    # Use assert_awaited_once() for AsyncMock
    mock_instantiate.assert_awaited_once()
