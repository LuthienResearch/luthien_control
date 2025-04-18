import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from luthien_control.config.settings import Settings
from luthien_control.core.policy_loader import ApiKeyLookupFunc, PolicyLoadError
from luthien_control.db.sqlmodel_crud import ControlPolicy, load_policy_from_db
from luthien_control.db.sqlmodel_models import ClientApiKey, Policy
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


@pytest.fixture
def load_db_mock_settings() -> Settings:
    """Provides mock Settings for load_policy_from_db tests."""
    return MagicMock(spec=Settings)


@pytest.fixture
def load_db_mock_http_client() -> httpx.AsyncClient:
    """Provides mock AsyncClient for load_policy_from_db tests."""
    return AsyncMock(spec=httpx.AsyncClient)


@pytest.fixture
def load_db_mock_api_key_lookup() -> ApiKeyLookupFunc:
    """Provides mock ApiKeyLookupFunc for load_policy_from_db tests."""

    async def _mock_lookup(key: str) -> ClientApiKey | None:
        if key == "valid-key":
            return ClientApiKey(key_value="valid-key", name="Test Key", is_active=True)
        return None

    return _mock_lookup


@pytest.fixture
def load_db_dependencies(
    load_db_mock_settings,
    load_db_mock_http_client,
    load_db_mock_api_key_lookup,
):
    """Bundles mock dependencies for load_policy_from_db tests."""
    return {
        "settings": load_db_mock_settings,
        "http_client": load_db_mock_http_client,
        "api_key_lookup_func": load_db_mock_api_key_lookup,
    }


def create_mock_policy_model(
    *,  # Enforce keyword-only arguments for clarity
    id: int = 1,
    name: str = "test_policy",
    policy_class_path: str = "luthien_control.tests.db.mock_policies.MockSimplePolicy",
    config: dict | None = None,
    is_active: bool = True,
    description: str | None = "A test policy",
    created_at: datetime.datetime | None = None,
    updated_at: datetime.datetime | None = None,
) -> Policy:
    """Helper to create mock Policy model instances for testing."""
    if config is None:
        config = {"timeout": 30}
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


# Mock the database fetch function used *within* load_policy_from_db
@patch("luthien_control.db.sqlmodel_crud.get_policy_by_name", new_callable=AsyncMock)
# Mock the actual policy instantiation logic
@patch("luthien_control.db.sqlmodel_crud.instantiate_policy", new_callable=AsyncMock)
async def test_load_policy_from_db_success(
    mock_instantiate,
    mock_get_policy_by_name,  # Renamed from mock_get_config for clarity
    load_db_dependencies,
    mock_db_session,  # Assuming mock_db_session comes from tests/conftest.py
):
    """Test successfully loading and instantiating a policy from DB config."""
    policy_name = "test_policy_success"
    mock_policy_config = create_mock_policy_model(name=policy_name)
    mock_get_policy_by_name.return_value = mock_policy_config

    # Mock the instantiated policy object that instantiate_policy should return
    mock_instantiated_policy = MagicMock(spec=ControlPolicy)
    mock_instantiate.return_value = mock_instantiated_policy

    # Call the function under test
    loaded_policy = await load_policy_from_db(
        name=policy_name,
        session=mock_db_session,  # Pass the mock session
        settings=load_db_dependencies["settings"],
        http_client=load_db_dependencies["http_client"],
        api_key_lookup=load_db_dependencies["api_key_lookup_func"],
    )

    # Assertions
    mock_get_policy_by_name.assert_awaited_once_with(mock_db_session, policy_name)
    # Assert instantiate_policy is called with the prepared config dict
    # (which includes name and class_path internally)
    expected_policy_config_arg = mock_policy_config.config or {}
    expected_policy_config_arg["name"] = mock_policy_config.name
    expected_policy_config_arg["policy_class_path"] = mock_policy_config.policy_class_path
    mock_instantiate.assert_awaited_once_with(
        policy_config=expected_policy_config_arg,
        settings=load_db_dependencies["settings"],
        http_client=load_db_dependencies["http_client"],
        api_key_lookup=load_db_dependencies["api_key_lookup_func"],
    )
    assert loaded_policy == mock_instantiated_policy


@patch("luthien_control.db.sqlmodel_crud.get_policy_by_name", new_callable=AsyncMock, return_value=None)
async def test_load_policy_from_db_not_found_patch_get(
    mock_get_policy_by_name,
    load_db_dependencies,
    mock_db_session,  # Keep using mock session for this specific variation
):
    """Test PolicyLoadError using PATCHED get_policy_by_name returning None."""
    # This test variant ensures the error is raised even if DB call is mocked
    policy_name = "non_existent_policy_patch"

    with pytest.raises(PolicyLoadError, match="not found in database"):
        await load_policy_from_db(
            name=policy_name,
            session=mock_db_session,
            settings=load_db_dependencies["settings"],
            http_client=load_db_dependencies["http_client"],
            api_key_lookup=load_db_dependencies["api_key_lookup_func"],
        )
    mock_get_policy_by_name.assert_awaited_once_with(mock_db_session, policy_name)


# Test using the actual DB session
async def test_load_policy_from_db_not_found_real_session(
    load_db_dependencies,
    async_session: AsyncSession,  # Use real session from tests/db/conftest.py
):
    """Test PolicyLoadError using a REAL session where the policy doesn't exist."""
    policy_name = "non_existent_policy_real"

    # Since the DB is empty, get_policy_by_name inside load_policy_from_db
    # will return None.
    with pytest.raises(PolicyLoadError, match="not found in database"):
        await load_policy_from_db(
            name=policy_name,
            session=async_session,  # Pass the real session
            settings=load_db_dependencies["settings"],
            http_client=load_db_dependencies["http_client"],
            api_key_lookup=load_db_dependencies["api_key_lookup_func"],
        )


# Keep the original patch for get_policy_by_name to ensure isolation if needed
# @patch("luthien_control.db.sqlmodel_crud.get_policy_by_name", new_callable=AsyncMock)
# Patch instantiate_policy to simulate failure
@patch(
    "luthien_control.db.sqlmodel_crud.instantiate_policy",
    new_callable=AsyncMock,
    side_effect=PolicyLoadError("Instantiation failed"),  # This is the initial error
)
async def test_load_policy_from_db_instantiation_fails(
    mock_instantiate,  # Keep patch for instantiate
    # mock_get_policy_by_name, # Remove patch for get_policy
    load_db_dependencies,
    async_session: AsyncSession,  # Use real session
):
    """Test PolicyLoadError when instantiate_policy fails, using real session."""
    policy_name = "instantiation_failure_policy"
    # Create the policy config in the real DB first
    policy_to_create = create_mock_policy_model(name=policy_name)
    # We need the actual create function now
    from luthien_control.db.sqlmodel_crud import create_policy

    created_policy = await create_policy(async_session, policy_to_create)
    assert created_policy is not None
    assert created_policy.name == policy_name

    # Match the *actual* error raised by the mock's side_effect,
    # which is caught and re-raised by the first except block.
    with pytest.raises(PolicyLoadError, match="Instantiation failed"):
        await load_policy_from_db(
            name=policy_name,
            session=async_session,  # Use real session
            settings=load_db_dependencies["settings"],
            http_client=load_db_dependencies["http_client"],
            api_key_lookup=load_db_dependencies["api_key_lookup_func"],
        )

    # mock_get_policy_by_name.assert_awaited_once_with(async_session, policy_name)
    mock_instantiate.assert_awaited_once()  # Verify instantiate was called


# Keep the original patch for get_policy_by_name to ensure isolation if needed
# @patch("luthien_control.db.sqlmodel_crud.get_policy_by_name", new_callable=AsyncMock)
async def test_load_policy_from_db_missing_class_path(
    # mock_get_policy_by_name, # Remove patch for get_policy
    load_db_dependencies,
    async_session: AsyncSession,  # Use real session
):
    """Test PolicyLoadError when fetched policy lacks class path, using real session."""
    policy_name = "missing_class_path_policy"
    # Create the policy config with None path in the real DB first
    policy_to_create = create_mock_policy_model(
        name=policy_name,
        policy_class_path=None,  # Explicitly set to None
    )
    # We need the actual create function now
    from luthien_control.db.sqlmodel_crud import create_policy

    created_policy = await create_policy(async_session, policy_to_create)
    assert created_policy is not None
    assert created_policy.name == policy_name
    assert created_policy.policy_class_path is None

    # Revert to pytest.raises with original match pattern (needs escaping for regex)
    with pytest.raises(PolicyLoadError, match="missing \\'policy_class_path\\'"):
        await load_policy_from_db(
            name=policy_name,
            session=async_session,  # Use real session
            settings=load_db_dependencies["settings"],
            http_client=load_db_dependencies["http_client"],
            api_key_lookup=load_db_dependencies["api_key_lookup_func"],
        )

    # mock_get_policy_by_name.assert_awaited_once_with(mock_db_session, policy_name)
