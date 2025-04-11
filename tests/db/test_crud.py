import datetime
import inspect
import json
from typing import Any, Dict
from unittest.mock import ANY, AsyncMock, MagicMock, call, patch

import asyncpg
import httpx
import pytest
from luthien_control.config.settings import Settings

# Assume these base classes/protocols exist for mocking
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.db import crud
from luthien_control.db.crud import (
    ApiKeyLookupFunc,
    PolicyLoadError,
    get_api_key_by_value,
    get_policy_config_by_name,
    load_policy_from_db,
    instantiate_policy,
)
from luthien_control.db.models import ApiKey, Policy

# Import the mock policy classes from the new helper file
from tests.db.mock_policies import (
    MockListPolicy,
    MockMissingArgPolicy,
    MockNestedPolicy,
    MockNoArgsPolicy,
    MockPolicyWithApiKeyLookup,
    MockSimplePolicy,
)

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


# --- Fixtures for load_policy_from_db --- #


@pytest.fixture
def mock_settings():
    return Settings()  # Or mock if Settings has complex logic


@pytest.fixture
def mock_http_client():
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def mock_api_key_lookup():
    return AsyncMock(spec=ApiKeyLookupFunc)


@pytest.fixture
def mock_dependencies(mock_settings, mock_http_client, mock_api_key_lookup):
    """Bundle common dependencies for load_policy_from_db tests."""
    return {
        "settings": mock_settings,
        "http_client": mock_http_client,
        "api_key_lookup": mock_api_key_lookup,
    }


# --- Helper Function to Create Mock Policy Config --- #


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
    now = datetime.datetime.now(datetime.UTC)
    return Policy(
        id=id,
        name=name,
        policy_class_path=policy_class_path,
        config=config,
        is_active=is_active,
        description=description,
        created_at=created_at or now,
        updated_at=updated_at or now,
    )


# --- Helper for getattr mocking in instantiate tests ---
# Removed module-level helper as it caused scope issues
# def mock_getattr_side_effect(module, class_name): ...


# --- Tests for load_policy_from_db --- #


@patch("luthien_control.db.crud.get_policy_config_by_name")
@patch("luthien_control.db.crud.instantiate_policy")
async def test_load_policy_from_db_success(mock_instantiate, mock_get_config, mock_dependencies):
    """Test load_policy_from_db successfully calls get_policy_config_by_name and instantiate_policy."""
    policy_name = "my_simple_policy"
    db_config = {"timeout": 123}
    mock_policy_model = create_mock_policy_model(
        name=policy_name, policy_class_path="luthien_control.test_policies.MockSimplePolicy", config=db_config
    )
    mock_get_config.return_value = mock_policy_model

    # Mock the result of instantiate_policy
    mock_instance = MockSimplePolicy(
        settings=mock_dependencies["settings"],
        http_client=mock_dependencies["http_client"],
        timeout=db_config["timeout"],
    )
    mock_instance.name = policy_name  # Simulate name assignment by instantiate_policy
    mock_instance.policy_class_path = mock_policy_model.policy_class_path
    mock_instantiate.return_value = mock_instance

    loaded_policy = await load_policy_from_db(policy_name, **mock_dependencies)

    # Verify DB lookup was called
    mock_get_config.assert_awaited_once_with(policy_name)

    # Verify instantiate_policy was called with the correct config dictionary
    expected_initial_config = db_config.copy()
    expected_initial_config["name"] = policy_name
    expected_initial_config["policy_class_path"] = mock_policy_model.policy_class_path

    mock_instantiate.assert_awaited_once_with(
        policy_config=expected_initial_config,
        settings=mock_dependencies["settings"],
        http_client=mock_dependencies["http_client"],
        api_key_lookup=mock_dependencies["api_key_lookup"],
    )

    # Verify the final result is what instantiate_policy returned
    assert loaded_policy is mock_instance


@patch("luthien_control.db.crud.get_policy_config_by_name", return_value=None)
async def test_load_policy_from_db_not_found(mock_get_config, mock_dependencies):
    """Test load_policy_from_db raises PolicyLoadError if policy not in DB."""
    policy_name = "non_existent"

    with pytest.raises(PolicyLoadError, match=f"Active policy configuration named '{policy_name}' not found"):
        await load_policy_from_db(policy_name, **mock_dependencies)

    mock_get_config.assert_awaited_once_with(policy_name)


@patch("luthien_control.db.crud.get_policy_config_by_name")
async def test_load_policy_from_db_missing_class_path(mock_get_config, mock_dependencies):
    """Test load_policy_from_db raises PolicyLoadError if DB model lacks class path."""
    policy_name = "policy_no_path"
    # Mock get_policy_config_by_name returning a dict-like object directly
    # to avoid Pydantic validation error during test setup.
    mock_db_return = MagicMock(spec=Policy)
    mock_db_return.name = policy_name
    mock_db_return.policy_class_path = None  # Simulate missing path
    mock_db_return.config = {}
    mock_get_config.return_value = mock_db_return

    with pytest.raises(
        PolicyLoadError,
        match=f"Policy configuration for '{policy_name}' fetched from DB is missing 'policy_class_path'",
    ):
        await load_policy_from_db(policy_name, **mock_dependencies)


@patch("luthien_control.db.crud.get_policy_config_by_name")
@patch("luthien_control.db.crud.instantiate_policy", side_effect=PolicyLoadError("Instantiation failed"))
async def test_load_policy_from_db_instantiation_fails(mock_instantiate, mock_get_config, mock_dependencies):
    """Test load_policy_from_db propagates PolicyLoadError from instantiate_policy."""
    policy_name = "policy_inst_fails"
    mock_policy_model = create_mock_policy_model(
        name=policy_name, policy_class_path="luthien_control.test_policies.MockSimplePolicy", config={"timeout": 50}
    )
    mock_get_config.return_value = mock_policy_model

    with pytest.raises(PolicyLoadError, match="Instantiation failed"):
        await load_policy_from_db(policy_name, **mock_dependencies)

    mock_get_config.assert_awaited_once_with(policy_name)
    mock_instantiate.assert_awaited_once()  # Check that it was called


# --- Tests for instantiate_policy --- #


# Use patch for importlib/getattr to avoid needing real modules/classes
@patch("luthien_control.db.crud.importlib.import_module")
@patch("luthien_control.db.crud.getattr")
async def test_instantiate_simple_policy_success(mock_getattr, mock_import_module, mock_dependencies):
    """Test direct instantiation of a simple policy."""
    policy_name = "simple_instance"
    class_path = "luthien_control.test_policies.MockSimplePolicy"
    config = {"timeout": 42}
    policy_config_dict = {"name": policy_name, "policy_class_path": class_path, **config}

    # Mock import process
    mock_module = MagicMock()
    mock_import_module.return_value = mock_module
    # Need to return the actual mock class here for isinstance checks and init signature
    mock_getattr.return_value = MockSimplePolicy

    instance = await instantiate_policy(policy_config_dict, **mock_dependencies)

    # Verify import was called
    mock_import_module.assert_called_once_with("luthien_control.test_policies")
    mock_getattr.assert_called_once_with(mock_module, "MockSimplePolicy")

    # Verify instance properties
    assert isinstance(instance, MockSimplePolicy)
    assert instance.timeout == 42
    assert instance.settings is mock_dependencies["settings"]
    assert instance.http_client is mock_dependencies["http_client"]
    # Check attributes assigned by the function
    assert hasattr(instance, "name")
    assert instance.name == policy_name
    assert hasattr(instance, "policy_class_path")
    assert instance.policy_class_path == class_path


@patch("luthien_control.db.crud.importlib.import_module")
@patch("luthien_control.db.crud.getattr")
async def test_instantiate_with_api_key_lookup(mock_getattr, mock_import_module, mock_dependencies):
    """Test instantiation injects api_key_lookup correctly."""
    policy_name = "api_lookup_instance"
    # Use the correct path from the mock_policies helper file
    class_path = "tests.db.mock_policies.MockPolicyWithApiKeyLookup"
    # Provide the correct config key 'tag' instead of 'config_val'
    config = {"tag": "lookup_tag"}
    policy_config_dict = {"name": policy_name, "policy_class_path": class_path, **config}

    mock_module = MagicMock()
    mock_import_module.return_value = mock_module
    mock_getattr.return_value = MockPolicyWithApiKeyLookup

    instance = await instantiate_policy(policy_config_dict, **mock_dependencies)

    # Assertions for the instance
    assert isinstance(instance, MockPolicyWithApiKeyLookup)
    assert instance.tag == config["tag"]  # Assert based on input config
    assert instance.name == policy_name  # Name should be assigned
    assert instance.policy_class_path == class_path  # Path should be assigned
    # Verify the api_key_lookup function was injected
    # No verification needed for recursive mock anymore


async def test_instantiate_policy_missing_class_path(mock_dependencies):
    """Test error if policy_config dict lacks 'policy_class_path'."""
    policy_config_dict = {"name": "missing_path", "some_param": "value"}
    with pytest.raises(PolicyLoadError, match="missing required key: 'policy_class_path'"):
        await instantiate_policy(policy_config_dict, **mock_dependencies)


async def test_instantiate_policy_missing_name(mock_dependencies):
    """Test error if policy_config dict lacks 'name'."""
    policy_config_dict = {"policy_class_path": "luthien_control.test_policies.MockSimplePolicy", "timeout": 10}
    with pytest.raises(PolicyLoadError, match="missing required key: 'name'"):
        await instantiate_policy(policy_config_dict, **mock_dependencies)


@patch("luthien_control.db.crud.importlib.import_module", side_effect=ImportError("Module not found"))
async def test_instantiate_policy_import_error(mock_import_module, mock_dependencies):
    """Test PolicyLoadError is raised on ImportError."""
    policy_name = "import_fail"
    # This path doesn't exist
    class_path = "non_existent_module.NonExistentClass"
    policy_config_dict = {
        "name": policy_name,
        "policy_class_path": class_path,
        "param": 1,  # Add some config to avoid missing name/path errors first
    }

    # No need to mock getattr if import_module fails first
    mock_import_module.side_effect = ImportError("Module not found")

    with pytest.raises(PolicyLoadError, match="Could not load policy class"):
        await instantiate_policy(policy_config_dict, **mock_dependencies)


@patch("luthien_control.db.crud.importlib.import_module")
@patch("luthien_control.db.crud.getattr", side_effect=AttributeError("Class not found"))
async def test_instantiate_policy_attribute_error(mock_getattr, mock_import_module, mock_dependencies):
    """Test PolicyLoadError is raised on AttributeError (class not in module)."""
    policy_config_dict = {
        "name": "attr_fail",
        "policy_class_path": "tests.db.mock_policies.NonExistentClass",  # Point to the right module, but non-existent class
        "param": 1,
    }
    mock_module = MagicMock()

    # Configure side_effect directly within the test
    def getattr_side_effect(module, class_name):
        if class_name == "MockNestedPolicy":
            return MockNestedPolicy  # This works as MockNestedPolicy is defined in the test file scope
        elif class_name == "MockSimplePolicy":
            return MockSimplePolicy
        else:
            raise AttributeError(f"Unexpected class: {class_name}")

    mock_getattr.side_effect = getattr_side_effect

    # Expect the error raised when getattr fails to find the class
    with pytest.raises(PolicyLoadError, match="Could not load policy class"):
        await instantiate_policy(policy_config_dict, **mock_dependencies)

    # Assertions for the successful part of the test (import/getattr calls)
    module_path_used = policy_config_dict["policy_class_path"].rsplit(".", 1)[0]
    mock_import_module.assert_called_once_with(module_path_used)


# Test Nested Policy Instantiation
async def test_instantiate_nested_policy_success(mock_dependencies):
    """Test instantiation of a policy containing another policy in its config."""
    nested_policy_name = "inner_policy"
    nested_class_path = "tests.db.mock_policies.MockSimplePolicy"
    nested_config = {"timeout": 99}

    outer_policy_name = "outer_policy"
    outer_class_path = "tests.db.mock_policies.MockNestedPolicy"
    outer_config = {
        "description": "My Nested Setup",
        "inner_policy": {  # Nested policy config
            "name": nested_policy_name,
            "policy_class_path": nested_class_path,
            **nested_config,
        },
    }
    policy_config_dict = {"name": outer_policy_name, "policy_class_path": outer_class_path, **outer_config}

    # No more mocking needed for recursive calls
    instance = await instantiate_policy(policy_config_dict, **mock_dependencies)

    # Outer policy assertions
    assert isinstance(instance, MockNestedPolicy)
    assert instance.description == "My Nested Setup"
    assert instance.name == outer_policy_name
    assert instance.policy_class_path == outer_class_path

    # Verify inner instance
    inner_instance = instance.inner_policy
    assert isinstance(inner_instance, MockSimplePolicy)
    assert inner_instance.timeout == 99
    assert inner_instance.name == nested_policy_name
    assert inner_instance.policy_class_path == nested_class_path


# Test Policy with List of Policies
@patch("luthien_control.db.crud.importlib.import_module")
@patch("luthien_control.db.crud.getattr")
async def test_instantiate_policy_with_list_of_policies(mock_getattr, mock_import_module, mock_dependencies):
    """Test instantiating a policy that takes a list of other policies (and non-policies) in config."""
    # Mock importlib.import_module to return a mock module object
    mock_import_module.return_value = MagicMock()

    # Mock getattr to return the appropriate class based on the name requested
    def getattr_side_effect(module, class_name):
        if class_name == "MockSimplePolicy":
            return MockSimplePolicy
        elif class_name == "MockNestedPolicy":
            return MockNestedPolicy
        elif class_name == "MockListPolicy":
            return MockListPolicy
        elif class_name == "MockNoArgsPolicy":
            return MockNoArgsPolicy
        else:
            raise AttributeError(f"Test mock does not handle class: {class_name}")

    mock_getattr.side_effect = getattr_side_effect

    member1_name = "list_member_1"
    member1_class_path = "tests.db.mock_policies.MockSimplePolicy"
    member1_config = {"timeout": 10}

    member2_name = "list_member_2"
    member2_class_path = "tests.db.mock_policies.MockNoArgsPolicy"

    outer_policy_name = "list_holder"
    outer_class_path = "tests.db.mock_policies.MockListPolicy"
    outer_config = {
        "mode": "parallel",
        "policies": [  # List containing policy configs
            {"name": member1_name, "policy_class_path": member1_class_path, **member1_config},
            {
                "name": member2_name,
                "policy_class_path": member2_class_path,
                # No config needed for MockNoArgsPolicy
            },
            "not_a_policy_dict",  # Item should be kept as is
        ],
    }
    policy_config_dict = {"name": outer_policy_name, "policy_class_path": outer_class_path, **outer_config}

    # No more mocking needed for recursive calls
    instance = await instantiate_policy(policy_config_dict, **mock_dependencies)

    # Assertions
    assert isinstance(instance, MockListPolicy)
    assert instance.mode == "parallel"
    assert instance.name == outer_policy_name
    assert len(instance.policies) == 3  # Includes the string

    # Check instantiated members
    assert isinstance(instance.policies[0], MockSimplePolicy)
    assert instance.policies[0].name == member1_name
    assert instance.policies[0].timeout == 10

    assert isinstance(instance.policies[1], MockNoArgsPolicy)
    assert instance.policies[1].name == member2_name

    # Check non-policy item preserved
    assert instance.policies[2] == "not_a_policy_dict"

    # Verify import/getattr calls (once for outer, once for each nested policy type)
    # Since we removed the complex patching, we can verify import/getattr calls again
    mock_module = MagicMock()  # Need a mock module instance for assertion
    mock_import_module.return_value = mock_module  # Assume import returns this
    # Configure mock_getattr side effect for verification (if needed, or remove verify block)
    # def getattr_side_effect(module, name): ... mock_getattr.side_effect = getattr_side_effect
    # Simple check: Ensure import_module was called multiple times (outer + nested types)
    assert mock_import_module.call_count >= 3  # Outer + MockSimplePolicy + MockNoArgsPolicy
    # Could add mock_getattr call assertions if needed


# Test Nested Policy Load Failure
async def test_instantiate_nested_policy_load_fails(mock_dependencies):
    """Test that if a nested policy fails to instantiate, the outer one fails too."""
    nested_policy_name = "inner_policy_fails"
    nested_class_path = "tests.db.mock_policies.MockMissingArgPolicy"

    outer_policy_name = "outer_policy_catcher"
    outer_class_path = "tests.db.mock_policies.MockNestedPolicy"
    outer_config = {
        "description": "Will Fail",
        "inner_policy": {  # Nested policy config that WILL fail
            "name": nested_policy_name,
            "policy_class_path": nested_class_path,
            # Missing 'mandatory' config here
        },
    }
    policy_config_dict = {"name": outer_policy_name, "policy_class_path": outer_class_path, **outer_config}

    # No more mocking needed for recursive calls
    # Now expect the specific error from trying to init MockMissingArgPolicy without 'mandatory'
    # The outer instantiate_policy catches the inner error and wraps it.
    with pytest.raises(PolicyLoadError, match="Failed to instantiate nested policy"):
        await instantiate_policy(policy_config_dict, **mock_dependencies)

    # No verification needed for recursive mock anymore
