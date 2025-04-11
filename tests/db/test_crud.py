import datetime
import inspect
import json
from typing import Any
from unittest.mock import ANY, AsyncMock, MagicMock, call, patch

import asyncpg
import httpx
import pytest
from luthien_control.config.settings import Settings
from luthien_control.control_policy.compound_policy import CompoundPolicy

# Assume these base classes/protocols exist for mocking
from luthien_control.control_policy.interface import ControlPolicy
from luthien_control.db import crud
from luthien_control.db.crud import (
    ApiKeyLookupFunc,
    PolicyLoadError,
    get_api_key_by_value,
    get_policy_config_by_name,
    load_policy_instance,
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


# --- Tests for load_policy_instance --- #


# --- Mock Policies --- #


class MockSimplePolicy(ControlPolicy):
    # Test injection of common deps + one config param
    def __init__(self, settings: Settings, http_client: httpx.AsyncClient, timeout: int = 10):
        self.settings = settings
        self.http_client = http_client
        self.timeout = timeout
        self.name = "DefaultSimplePolicyName"
        # Mock apply method required by protocol

    async def apply(self, context):
        pass

    def serialize_config(self) -> dict[str, Any]:
        return {}


class MockPolicyWithApiKeyLookup(ControlPolicy):
    # Test injection of api_key_lookup
    def __init__(self, api_key_lookup: ApiKeyLookupFunc, config_val: str):
        self.api_key_lookup = api_key_lookup
        self.config_val = config_val
        self.name = "DefaultApiKeyPolicyName"

    async def apply(self, context):
        pass

    def serialize_config(self) -> dict[str, Any]:
        return {}


class MockNoArgsPolicy(ControlPolicy):
    def __init__(self):
        self.name = "DefaultNoArgsPolicyName"

    async def apply(self, context):
        pass

    def serialize_config(self) -> dict[str, Any]:
        return {}


class MockCompoundPolicy(CompoundPolicy):
    # Use the real CompoundPolicy structure for testing issubclass and arg passing
    def __init__(self, policies: list[ControlPolicy], name: str = "MockCompound"):
        # Don't call super().__init__ to avoid needing real policies
        self.policies = policies
        self.name = name
        self.logger = MagicMock()

    async def apply(self, context):
        pass

    def serialize_config(self) -> dict[str, Any]:
        # For consistency in this test file's mocks, return empty dict.
        # The real CompoundPolicy has its own serialization.
        return {}


class MockMissingArgPolicy(ControlPolicy):
    # Missing required argument `required_arg`
    def __init__(self, settings: Settings):
        self.settings = settings
        self.name = "DefaultMissingArgPolicyName"

    async def apply(self, context):
        pass

    def serialize_config(self) -> dict[str, Any]:
        return {}


# --- Fixtures for load_policy_instance --- #


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
    """Bundle common dependencies for load_policy_instance tests."""
    return {
        "settings": mock_settings,
        "http_client": mock_http_client,
        "api_key_lookup": mock_api_key_lookup,
    }


# --- Helper Function to Create Mock Policy Config --- #


def create_mock_policy_config(
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


# --- Test Cases --- #


@patch.object(crud, "get_policy_config_by_name")
@patch("luthien_control.db.crud.importlib.import_module")
@patch("luthien_control.db.crud.getattr")
@patch("luthien_control.db.crud.inspect.signature")
async def test_load_simple_policy_success(
    mock_inspect_sig, mock_getattr, mock_import_module, mock_get_config, mock_dependencies
):
    """Test successfully loading a simple policy with dependency injection and config."""
    policy_name = "simple_policy_instance"
    policy_class_path = "luthien_control.test_policies.MockSimplePolicy"
    db_config = {"timeout": 30}
    mock_policy_config = create_mock_policy_config(
        name=policy_name, policy_class_path=policy_class_path, config=db_config
    )

    async def fake_get_config(name):
        if name == policy_name:
            return mock_policy_config
        return None

    mock_get_config.side_effect = fake_get_config

    mock_module = MagicMock()
    mock_import_module.return_value = mock_module
    mock_getattr.return_value = MockSimplePolicy

    mock_sig = MagicMock(spec=inspect.Signature)
    mock_sig.parameters = {
        "self": inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD),
        "settings": inspect.Parameter("settings", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Settings),
        "http_client": inspect.Parameter(
            "http_client", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=httpx.AsyncClient
        ),
        "timeout": inspect.Parameter("timeout", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=int, default=10),
    }
    mock_inspect_sig.return_value = mock_sig

    instance = await load_policy_instance(policy_name, **mock_dependencies)

    mock_get_config.assert_awaited_once_with(policy_name)
    mock_import_module.assert_called_once_with("luthien_control.test_policies")
    mock_getattr.assert_called_once_with(mock_module, "MockSimplePolicy")
    mock_inspect_sig.assert_called_with(MockSimplePolicy.__init__)

    assert isinstance(instance, MockSimplePolicy)
    assert instance.settings is mock_dependencies["settings"]
    assert instance.http_client is mock_dependencies["http_client"]
    assert instance.timeout == 30  # Value from db_config used
    assert instance.name == policy_name  # Name assigned from config


@patch.object(crud, "get_policy_config_by_name")
@patch("luthien_control.db.crud.importlib.import_module")
@patch("luthien_control.db.crud.getattr")
@patch("luthien_control.db.crud.inspect.signature")
async def test_load_policy_with_api_key_lookup(
    mock_inspect_sig, mock_getattr, mock_import_module, mock_get_config, mock_dependencies
):
    """Test successfully loading a policy requiring api_key_lookup."""
    policy_name = "api_key_policy"
    policy_class_path = "luthien_control.test_policies.MockPolicyWithApiKeyLookup"
    db_config = {"config_val": "test_value"}
    mock_policy_config = create_mock_policy_config(
        name=policy_name, policy_class_path=policy_class_path, config=db_config
    )

    async def fake_get_config(name):
        if name == policy_name:
            return mock_policy_config
        return None

    mock_get_config.side_effect = fake_get_config

    mock_module = MagicMock()
    mock_import_module.return_value = mock_module
    mock_getattr.return_value = MockPolicyWithApiKeyLookup

    mock_sig = MagicMock(spec=inspect.Signature)
    mock_sig.parameters = {
        "self": inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD),
        "api_key_lookup": inspect.Parameter(
            "api_key_lookup", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=ApiKeyLookupFunc
        ),
        "config_val": inspect.Parameter("config_val", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str),
    }
    mock_inspect_sig.return_value = mock_sig

    instance = await load_policy_instance(policy_name, **mock_dependencies)

    assert isinstance(instance, MockPolicyWithApiKeyLookup)
    assert instance.api_key_lookup is mock_dependencies["api_key_lookup"]
    assert instance.config_val == "test_value"
    assert instance.name == policy_name


@patch.object(crud, "get_policy_config_by_name")
async def test_load_policy_not_found(mock_get_config, mock_dependencies):
    """Test PolicyLoadError when policy config is not found in DB."""
    policy_name = "not_a_real_policy"

    async def fake_get_config(name):
        return None

    mock_get_config.side_effect = fake_get_config

    with pytest.raises(PolicyLoadError, match=f"Active policy configuration named '{policy_name}' not found"):
        await load_policy_instance(policy_name, **mock_dependencies)
    mock_get_config.assert_awaited_once_with(policy_name)


@patch.object(crud, "get_policy_config_by_name")
@patch("luthien_control.db.crud.importlib.import_module", side_effect=ImportError("Module not found"))
async def test_load_policy_import_error(mock_import_module, mock_get_config, mock_dependencies):
    """Test PolicyLoadError when the policy module cannot be imported."""
    policy_name = "import_error_policy"
    policy_class_path = "nonexistent.module.PolicyClass"
    mock_policy_config = create_mock_policy_config(name=policy_name, policy_class_path=policy_class_path)

    async def fake_get_config(name):
        if name == policy_name:
            return mock_policy_config
        return None

    mock_get_config.side_effect = fake_get_config

    with pytest.raises(PolicyLoadError, match=f"Could not load policy class '{policy_class_path}'"):
        await load_policy_instance(policy_name, **mock_dependencies)
    mock_get_config.assert_awaited_once_with(policy_name)
    mock_import_module.assert_called_once_with("nonexistent.module")


@patch.object(crud, "get_policy_config_by_name")
@patch("luthien_control.db.crud.importlib.import_module")
@patch("luthien_control.db.crud.getattr", side_effect=AttributeError("Class not found"))
async def test_load_policy_attribute_error(mock_getattr, mock_import_module, mock_get_config, mock_dependencies):
    """Test PolicyLoadError when the policy class is not found in the module."""
    policy_name = "attr_error_policy"
    policy_class_path = "some.module.WrongClassName"
    mock_policy_config = create_mock_policy_config(name=policy_name, policy_class_path=policy_class_path)

    async def fake_get_config(name):
        if name == policy_name:
            return mock_policy_config
        return None

    mock_get_config.side_effect = fake_get_config

    mock_module = MagicMock()
    mock_import_module.return_value = mock_module

    with pytest.raises(PolicyLoadError, match=f"Could not load policy class '{policy_class_path}'"):
        await load_policy_instance(policy_name, **mock_dependencies)
    mock_get_config.assert_awaited_once_with(policy_name)
    mock_import_module.assert_called_once_with("some.module")
    mock_getattr.assert_called_once_with(mock_module, "WrongClassName")


@patch.object(crud, "get_policy_config_by_name")
@patch("luthien_control.db.crud.importlib.import_module")
@patch("luthien_control.db.crud.getattr")
@patch("luthien_control.db.crud.inspect.signature")
async def test_load_policy_missing_required_arg(
    mock_inspect_sig, mock_getattr, mock_import_module, mock_get_config, mock_dependencies
):
    """Test PolicyLoadError when a required __init__ arg is missing."""
    policy_name = "missing_arg_policy"
    policy_class_path = "luthien_control.test_policies.MockMissingArgPolicy"
    mock_policy_config = create_mock_policy_config(name=policy_name, policy_class_path=policy_class_path, config={})

    async def fake_get_config(name):
        if name == policy_name:
            return mock_policy_config
        return None

    mock_get_config.side_effect = fake_get_config

    mock_module = MagicMock()
    mock_import_module.return_value = mock_module
    mock_getattr.return_value = MockMissingArgPolicy

    # Simulate signature requiring 'required_arg' which is not in config or dependencies
    mock_sig = MagicMock(spec=inspect.Signature)
    mock_sig.parameters = {
        "self": inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD),
        "settings": inspect.Parameter("settings", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Settings),
        "required_arg": inspect.Parameter("required_arg", inspect.Parameter.POSITIONAL_OR_KEYWORD),  # Required
    }
    mock_inspect_sig.return_value = mock_sig

    with pytest.raises(PolicyLoadError, match=r"Missing required arguments: \['required_arg'\]"):
        await load_policy_instance(policy_name, **mock_dependencies)

    mock_get_config.assert_awaited_once_with(policy_name)
    mock_import_module.assert_called_once_with("luthien_control.test_policies")
    mock_getattr.assert_called_once_with(mock_module, "MockMissingArgPolicy")
    mock_inspect_sig.assert_called_with(MockMissingArgPolicy.__init__)


@patch.object(crud, "logger")
@patch.object(crud, "get_policy_config_by_name")
@patch("luthien_control.db.crud.importlib.import_module")
@patch("luthien_control.db.crud.getattr")
@patch("luthien_control.db.crud.inspect.signature")
async def test_load_policy_config_ignored_if_not_in_init(
    mock_inspect_sig, mock_getattr, mock_import_module, mock_get_config, mock_logger, mock_dependencies
):
    """Test that config keys not in __init__ are ignored (with warning)."""
    # mock_logger is now the patched crud.logger instance

    policy_name = "ignored_config_policy"
    policy_class_path = "luthien_control.test_policies.MockNoArgsPolicy"
    db_config = {"ignored_key": "some_value", "another_ignored": 123}
    mock_policy_config = create_mock_policy_config(
        name=policy_name, policy_class_path=policy_class_path, config=db_config
    )
    # Revert async side_effect and use await_value
    mock_get_config.return_value = mock_policy_config
    mock_get_config.await_value = mock_policy_config

    mock_module = MagicMock()
    mock_import_module.return_value = mock_module
    mock_getattr.return_value = MockNoArgsPolicy

    mock_sig = MagicMock(spec=inspect.Signature)
    mock_sig.parameters = {"self": inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD)}
    mock_inspect_sig.return_value = mock_sig

    # Patch the 'warning' method on the already-patched logger object
    with patch.object(mock_logger, "warning") as mock_warning_method:
        instance = await load_policy_instance(policy_name, **mock_dependencies)

    assert isinstance(instance, MockNoArgsPolicy)
    assert instance.name == policy_name

    # Assert on the warning method mock created by the inner patch
    assert mock_warning_method.call_count == 2
    mock_warning_method.assert_has_calls(
        [
            call(ANY),  # First call argument
            call(ANY),  # Second call argument
        ],
        any_order=True,
    )
    # Optionally check content if needed:
    assert "ignored_key" in mock_warning_method.call_args_list[0].args[0]
    assert "another_ignored" in mock_warning_method.call_args_list[1].args[0]
    assert "does not match any parameter" in mock_warning_method.call_args_list[0].args[0]
    assert "does not match any parameter" in mock_warning_method.call_args_list[1].args[0]

    mock_inspect_sig.assert_called_with(MockNoArgsPolicy.__init__)


# --- Tests for CompoundPolicy Loading --- #


@patch.object(crud, "get_policy_config_by_name")
@patch("luthien_control.db.crud.importlib.import_module")
@patch("luthien_control.db.crud.getattr")
@patch("luthien_control.db.crud.inspect.signature")
async def test_load_compound_policy_success(
    mock_inspect_sig, mock_getattr, mock_import_module, mock_get_config, mock_dependencies
):
    """Test loading a CompoundPolicy with two simple members."""
    compound_policy_name = "compound_root"
    member1_name = "member_policy_1"
    member2_name = "member_policy_2"
    compound_class_path = "luthien_control.control_policy.compound_policy.MockCompoundPolicy"
    member_class_path = "luthien_control.test_policies.MockNoArgsPolicy"

    # Mock configs for compound and members
    compound_config = create_mock_policy_config(
        name=compound_policy_name,
        policy_class_path=compound_class_path,
        config={"member_policy_names": [member1_name, member2_name]},
    )
    member1_config = create_mock_policy_config(id=2, name=member1_name, policy_class_path=member_class_path, config={})
    member2_config = create_mock_policy_config(id=3, name=member2_name, policy_class_path=member_class_path, config={})

    # Configure mock_get_config to return the correct config based on name
    async def async_get_config_compound(name):
        config_map = {
            compound_policy_name: compound_config,
            member1_name: member1_config,
            member2_name: member2_config,
        }
        return config_map.get(name)

    mock_get_config.side_effect = async_get_config_compound

    # Configure mocks for import/getattr/signature
    mock_module_compound = MagicMock()
    mock_module_noargs = MagicMock()
    mock_import_module.side_effect = lambda path: {
        "luthien_control.control_policy.compound_policy": mock_module_compound,
        "luthien_control.test_policies": mock_module_noargs,
    }.get(path)

    mock_getattr.side_effect = lambda module, cls_name: {
        (mock_module_compound, "MockCompoundPolicy"): MockCompoundPolicy,
        (mock_module_noargs, "MockNoArgsPolicy"): MockNoArgsPolicy,
    }.get((module, cls_name))

    # Mock signatures for Compound and NoArgs
    sig_compound = MagicMock(spec=inspect.Signature)
    sig_compound.parameters = {
        "self": inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD),
        "policies": inspect.Parameter(
            "policies", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=list[ControlPolicy]
        ),
        "name": inspect.Parameter(
            "name", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str, default="MockCompound"
        ),
    }
    sig_noargs = MagicMock(spec=inspect.Signature)
    sig_noargs.parameters = {
        "self": inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD),
    }
    mock_inspect_sig.side_effect = lambda func: {
        MockCompoundPolicy.__init__: sig_compound,
        MockNoArgsPolicy.__init__: sig_noargs,
    }.get(func)

    # --- Call the function under test --- #
    instance = await load_policy_instance(compound_policy_name, **mock_dependencies)

    # --- Assertions --- #
    assert isinstance(instance, MockCompoundPolicy)
    assert instance.name == compound_policy_name
    assert len(instance.policies) == 2
    assert isinstance(instance.policies[0], MockNoArgsPolicy)
    assert instance.policies[0].name == member1_name  # Name assigned from member config
    assert isinstance(instance.policies[1], MockNoArgsPolicy)
    assert instance.policies[1].name == member2_name  # Name assigned from member config

    # Check get_policy_config_by_name calls
    assert mock_get_config.call_count == 3
    mock_get_config.assert_has_calls(
        [
            call(compound_policy_name),
            call(member1_name),
            call(member2_name),
        ],
        any_order=True,
    )  # Order might vary due to async nature

    # Check import/getattr/signature calls
    assert mock_import_module.call_count == 3
    assert mock_getattr.call_count == 3
    mock_inspect_sig.assert_has_calls(
        [call(MockCompoundPolicy.__init__), call(MockNoArgsPolicy.__init__)], any_order=True
    )


@patch.object(crud, "get_policy_config_by_name")
@patch("luthien_control.db.crud.importlib.import_module")
@patch("luthien_control.db.crud.getattr")
@patch("luthien_control.db.crud.inspect.signature")
async def test_load_compound_policy_circular_dependency(
    mock_inspect_sig, mock_getattr, mock_import_module, mock_get_config, mock_dependencies
):
    """Test PolicyLoadError for circular dependency in CompoundPolicy."""
    policy1_name = "policy_circle_1"
    policy2_name = "policy_circle_2"
    compound_class_path = "luthien_control.control_policy.compound_policy.MockCompoundPolicy"

    # Configs where policy1 contains policy2, and policy2 contains policy1
    config1 = create_mock_policy_config(
        id=1, name=policy1_name, policy_class_path=compound_class_path, config={"member_policy_names": [policy2_name]}
    )
    config2 = create_mock_policy_config(
        id=2, name=policy2_name, policy_class_path=compound_class_path, config={"member_policy_names": [policy1_name]}
    )

    # Mock get_config - Keep async side_effect
    async def async_get_config_circular(name):
        config_map = {policy1_name: config1, policy2_name: config2}
        return config_map.get(name)

    mock_get_config.side_effect = async_get_config_circular

    # Mock import/getattr/signature (only MockCompoundPolicy needed)
    mock_module = MagicMock()
    mock_import_module.return_value = mock_module
    mock_getattr.return_value = MockCompoundPolicy

    sig_compound = MagicMock(spec=inspect.Signature)
    sig_compound.parameters = {
        "self": inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD),
        "policies": inspect.Parameter(
            "policies", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=list[ControlPolicy]
        ),
        "name": inspect.Parameter(
            "name", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str, default="MockCompound"
        ),
    }
    mock_inspect_sig.return_value = sig_compound

    # Expect PolicyLoadError due to circular dependency
    with pytest.raises(
        PolicyLoadError, match="Failed to load member policy 'policy_circle_2' for CompoundPolicy 'policy_circle_1'"
    ):
        await load_policy_instance(policy1_name, **mock_dependencies)

    # Check get_config was called for both
    assert mock_get_config.call_count == 2
    mock_get_config.assert_has_calls([call(policy1_name), call(policy2_name)], any_order=True)


@patch.object(crud, "get_policy_config_by_name")
@patch("luthien_control.db.crud.importlib.import_module")
@patch("luthien_control.db.crud.getattr")
@patch("luthien_control.db.crud.inspect.signature")
async def test_load_compound_policy_member_load_fails(
    mock_inspect_sig, mock_getattr, mock_import_module, mock_get_config, mock_dependencies
):
    """Test that loading a compound policy fails if a member policy fails to load."""
    compound_policy_name = "compound_fail"
    member_ok_name = "member_ok"
    member_fail_name = "member_fail"
    compound_class_path = "luthien_control.control_policy.compound_policy.MockCompoundPolicy"
    member_ok_class_path = "luthien_control.test_policies.MockNoArgsPolicy"

    # Configs: compound contains ok and fail members. fail member config is missing.
    compound_config = create_mock_policy_config(
        name=compound_policy_name,
        policy_class_path=compound_class_path,
        config={"member_policy_names": [member_ok_name, member_fail_name]},
    )
    member_ok_config = create_mock_policy_config(
        id=2, name=member_ok_name, policy_class_path=member_ok_class_path, config={}
    )
    # member_fail_config is missing -> mock_get_config returns None for it

    # Keep async side_effect
    async def async_get_config_fail(name):
        config_map = {
            compound_policy_name: compound_config,
            member_ok_name: member_ok_config,
            member_fail_name: None,  # Simulate failure to find config
        }
        return config_map.get(name)

    mock_get_config.side_effect = async_get_config_fail

    # Mocks for import/getattr/signature (only need Compound and NoArgs)
    mock_module_compound = MagicMock()
    mock_module_noargs = MagicMock()
    mock_import_module.side_effect = lambda path: {
        "luthien_control.control_policy.compound_policy": mock_module_compound,
        "luthien_control.test_policies": mock_module_noargs,
    }.get(path)

    mock_getattr.side_effect = lambda module, cls_name: {
        (mock_module_compound, "MockCompoundPolicy"): MockCompoundPolicy,
        (mock_module_noargs, "MockNoArgsPolicy"): MockNoArgsPolicy,
    }.get((module, cls_name))

    sig_compound = MagicMock(spec=inspect.Signature)
    sig_compound.parameters = {
        "self": inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD),
        "policies": inspect.Parameter(
            "policies", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=list[ControlPolicy]
        ),
        "name": inspect.Parameter(
            "name", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=str, default="MockCompound"
        ),
    }
    sig_noargs = MagicMock(spec=inspect.Signature)
    sig_noargs.parameters = {
        "self": inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD),
    }
    mock_inspect_sig.side_effect = lambda func: {
        MockCompoundPolicy.__init__: sig_compound,
        MockNoArgsPolicy.__init__: sig_noargs,
    }.get(func)

    # Expect failure when loading member_fail
    with pytest.raises(PolicyLoadError, match=f"Failed to load member policy '{member_fail_name}'"):
        await load_policy_instance(compound_policy_name, **mock_dependencies)

    # Check get_config calls (compound, ok, fail)
    assert mock_get_config.call_count == 3
    mock_get_config.assert_has_calls(
        [call(compound_policy_name), call(member_ok_name), call(member_fail_name)], any_order=True
    )
