from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from luthien_control.control_policy.control_policy import (
    ControlPolicy as BaseControlPolicy,
)
from luthien_control.control_policy.exceptions import PolicyLoadError
from luthien_control.control_policy.serialization import SerializedPolicy
from luthien_control.db.control_policy_crud import (
    get_policy_by_name,
    get_policy_config_by_name,
    list_policies,
    load_policy_from_db,
    save_policy_to_db,
    update_policy,
)
from luthien_control.db.exceptions import (
    LuthienDBIntegrityError,
    LuthienDBOperationError,
    LuthienDBQueryError,
    LuthienDBTransactionError,
)
from luthien_control.db.sqlmodel_models import ControlPolicy
from pytest_mock import MockerFixture
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
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
    created_policy_val = await save_policy_to_db(async_session, policy)
    assert created_policy_val is not None
    created_policy = cast(ControlPolicy, created_policy_val)
    assert created_policy.id is not None
    assert created_policy.type == "mock_type"

    # Retrieve the policy by name
    retrieved_policy_val = await get_policy_by_name(async_session, "test-policy")
    assert retrieved_policy_val is not None
    retrieved_policy = cast(ControlPolicy, retrieved_policy_val)
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
    created_policy_val = await save_policy_to_db(async_session, policy)
    assert created_policy_val is not None
    created_policy = cast(ControlPolicy, created_policy_val)
    assert created_policy.id is not None  # Ensure ID is assigned

    # Update the policy
    # Pass a Policy model instance for the update payload
    update_payload = ControlPolicy(
        name="update-policy",  # Not strictly needed by update func
        type="mock_type_updated",  # type is Optional, but good to provide if changed
        config={"updated": True},
        description="Updated description",
        is_active=False,  # Example change
    )

    updated_policy_val = await update_policy(async_session, created_policy.id, update_payload)
    assert updated_policy_val is not None
    updated_policy = cast(ControlPolicy, updated_policy_val)
    assert updated_policy.id is not None  # Check id after update
    assert updated_policy.config == {"updated": True}
    assert updated_policy.description == "Updated description"
    assert updated_policy.is_active is False

    # Verify the update persisted
    # get_policy_by_name only returns active policies by default in its current impl.
    # If we want to check the updated (now inactive) policy, we'd need to adjust the query
    # or use a different retrieval method if one exists that gets inactive policies by name.
    # For now, the existing test logic checks that it's NOT found by the default get_policy_by_name.
    retrieved_policy_after_update = await get_policy_by_name(async_session, "update-policy")
    assert retrieved_policy_after_update is None


async def test_update_policy_not_found(async_session: AsyncSession):
    """Test updating a non-existent policy."""
    # Pass a Policy model instance
    update_payload = ControlPolicy(name="non-existent-policy", type="dummy_type", description="Updated description")
    updated_policy = await update_policy(async_session, 9999, update_payload)  # Non-existent ID
    assert updated_policy is None


async def test_get_policy_by_name_not_found(async_session: AsyncSession):
    """Test getting a non-existent policy by name."""
    retrieved_policy = await get_policy_by_name(async_session, "non-existent-policy")
    assert retrieved_policy is None


async def test_create_policy_duplicate_name(async_session: AsyncSession):
    """Test creating a policy with a name that already exists."""
    policy1 = ControlPolicy(name="duplicate-name", type="mock_type")
    created_policy1_val = await save_policy_to_db(async_session, policy1)
    assert created_policy1_val is not None  # Ensure first creation succeeded
    created_policy1 = cast(ControlPolicy, created_policy1_val)
    assert created_policy1.id is not None

    # 'type' is optional, but name is required.
    policy2 = ControlPolicy(name="duplicate-name", type="another_mock_type")
    # Expecting LuthienDBIntegrityError because the function now wraps IntegrityError
    with pytest.raises(LuthienDBIntegrityError, match="Could not create policy due to constraint violation"):
        await save_policy_to_db(async_session, policy2)


async def test_load_policy_from_db_happy_path(mocker: MockerFixture):
    """Test successfully loading a policy from the database."""
    mock_db_session = AsyncMock()
    mock_container = MagicMock()
    # Configure the mock_container's db_session_factory to be an async context manager
    mock_container.db_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_container.db_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    policy_name = "test_policy"
    # This is the DB model representation
    db_policy_model = ControlPolicy(
        id=1,
        name=policy_name,
        type="mock_policy_type",
        config={"key": "value"},
        is_active=True,
    )

    # Mock the call to get_policy_by_name within load_policy_from_db
    mock_get_policy_by_name = mocker.patch(
        "luthien_control.db.control_policy_crud.get_policy_by_name",
        return_value=db_policy_model,
    )

    # Mock the call to the external load_policy function
    # This is the instantiated policy object
    mock_instantiated_policy = MagicMock(spec=BaseControlPolicy)
    mock_instantiated_policy.name = policy_name
    mock_load_policy = mocker.patch(
        "luthien_control.db.control_policy_crud.load_policy",
        return_value=mock_instantiated_policy,
    )

    result = await load_policy_from_db(policy_name, mock_container)

    mock_get_policy_by_name.assert_awaited_once_with(mock_db_session, policy_name)
    expected_policy_data = SerializedPolicy(
        type=db_policy_model.type,
        config=db_policy_model.config or {},
    )
    mock_load_policy.assert_called_once_with(expected_policy_data)
    assert result is mock_instantiated_policy
    assert result.name == policy_name


async def test_load_policy_from_db_not_found(mocker: MockerFixture):
    """Test PolicyLoadError when policy is not found by get_policy_by_name."""
    mock_db_session = AsyncMock()
    mock_container = MagicMock()
    mock_container.db_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_container.db_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    policy_name = "non_existent_policy"

    mock_get_policy_by_name = mocker.patch(
        "luthien_control.db.control_policy_crud.get_policy_by_name",
        return_value=None,  # Simulate policy not found
    )
    # Patch load_policy as it might be called if the error isn't raised first
    mock_load_policy = mocker.patch("luthien_control.db.control_policy_crud.load_policy")

    with pytest.raises(
        PolicyLoadError,
        match=f"Active policy configuration named '{policy_name}' not found in database.",
    ):
        await load_policy_from_db(policy_name, mock_container)

    mock_get_policy_by_name.assert_awaited_once_with(mock_db_session, policy_name)
    mock_load_policy.assert_not_called()


async def test_load_policy_from_db_loader_raises_policy_load_error(
    mocker: MockerFixture,
):
    """Test re-raising PolicyLoadError from the loader."""
    mock_db_session = AsyncMock()
    mock_container = MagicMock()
    mock_container.db_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_container.db_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    policy_name = "test_policy_loader_fail"
    db_policy_model = ControlPolicy(id=1, name=policy_name, type="failing_type", config={}, is_active=True)

    mocker.patch(
        "luthien_control.db.control_policy_crud.get_policy_by_name",
        return_value=db_policy_model,
    )

    original_error = PolicyLoadError("Loader failed for specific reason")
    mock_load_policy = mocker.patch(
        "luthien_control.db.control_policy_crud.load_policy",
        side_effect=original_error,
    )

    with pytest.raises(PolicyLoadError) as exc_info:
        await load_policy_from_db(policy_name, mock_container)

    assert exc_info.value is original_error
    mock_load_policy.assert_called_once()


async def test_load_policy_from_db_loader_raises_other_exception(
    mocker: MockerFixture,
):
    """Test wrapping other exceptions from loader in PolicyLoadError."""
    mock_db_session = AsyncMock()
    mock_container = MagicMock()
    mock_container.db_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_db_session)
    mock_container.db_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    policy_name = "test_policy_loader_unexpected_fail"
    db_policy_model = ControlPolicy(id=1, name=policy_name, type="buggy_type", config={}, is_active=True)

    mocker.patch(
        "luthien_control.db.control_policy_crud.get_policy_by_name",
        return_value=db_policy_model,
    )

    original_exception = ValueError("Some unexpected value error in loader")
    mock_load_policy = mocker.patch(
        "luthien_control.db.control_policy_crud.load_policy",
        side_effect=original_exception,
    )

    with pytest.raises(
        PolicyLoadError,
        match=f"Unexpected error during loading process for '{policy_name}'.",
    ) as exc_info:
        await load_policy_from_db(policy_name, mock_container)

    assert exc_info.value.__cause__ is original_exception
    mock_load_policy.assert_called_once()


async def test_load_policy_from_db_db_query_error(mocker: MockerFixture):
    """Test load_policy_from_db when get_policy_by_name raises a LuthienDBQueryError."""
    mock_container = MagicMock()
    mock_session = AsyncMock()
    mock_container.db_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_container.db_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    policy_name = "test_policy_db_query_error"
    db_error = LuthienDBQueryError("Database query failed")

    mocker.patch(
        "luthien_control.db.control_policy_crud.get_policy_by_name",
        side_effect=db_error,
    )

    with pytest.raises(LuthienDBQueryError, match="Database query failed"):
        await load_policy_from_db(policy_name, mock_container)


async def test_load_policy_from_db_unexpected_exception(mocker: MockerFixture):
    """Test load_policy_from_db when an unexpected exception occurs outside the loader."""
    mock_container = MagicMock()
    mock_session = AsyncMock()
    mock_container.db_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_container.db_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    policy_name = "test_policy_unexpected_error"
    error_message = "Unexpected error"

    mocker.patch(
        "luthien_control.db.control_policy_crud.get_policy_by_name",
        side_effect=Exception(error_message),
    )

    # Mock logger to check if error is logged
    mock_logger_exception = mocker.patch("luthien_control.db.control_policy_crud.logger.exception")

    # Function should wrap the exception in a PolicyLoadError
    with pytest.raises(PolicyLoadError, match=f"Unexpected error during loading process for '{policy_name}'"):
        await load_policy_from_db(policy_name, mock_container)

    mock_logger_exception.assert_called_once_with(
        f"Unexpected error during policy loading process for '{policy_name}': {error_message}"
    )


async def test_get_policy_config_by_name_found_active(async_session: AsyncSession):
    """Test getting an active policy config by name."""
    policy_name = "config_test_active"
    policy = ControlPolicy(name=policy_name, type="test_type", config={"data": "active"}, is_active=True)
    await save_policy_to_db(async_session, policy)

    retrieved_config = await get_policy_config_by_name(async_session, policy_name)
    assert retrieved_config is not None
    assert retrieved_config.name == policy_name
    assert retrieved_config.is_active is True
    assert retrieved_config.config == {"data": "active"}


async def test_get_policy_config_by_name_found_inactive(async_session: AsyncSession):
    """Test getting an inactive policy config by name."""
    policy_name = "config_test_inactive"
    policy = ControlPolicy(name=policy_name, type="test_type", config={"data": "inactive"}, is_active=False)
    await save_policy_to_db(async_session, policy)

    retrieved_config = await get_policy_config_by_name(async_session, policy_name)
    assert retrieved_config is not None
    assert retrieved_config.name == policy_name
    assert retrieved_config.is_active is False
    assert retrieved_config.config == {"data": "inactive"}


async def test_get_policy_config_by_name_not_found(async_session: AsyncSession):
    """Test getting a non-existent policy config by name returns None."""
    retrieved_config = await get_policy_config_by_name(async_session, "non_existent_config_policy")
    assert retrieved_config is None


async def test_get_policy_config_by_name_invalid_session_type():
    """Test TypeError is raised for invalid session type."""
    # Using a MagicMock that is not an AsyncSession instance
    invalid_session = MagicMock()
    with pytest.raises(
        TypeError,
        match="Invalid session object provided to get_policy_config_by_name.",
    ):
        await get_policy_config_by_name(invalid_session, "any_name")


async def test_get_policy_config_by_name_db_error(mocker: MockerFixture):
    """Test generic exception during DB fetch raises LuthienDBOperationError."""
    mock_session = AsyncMock(spec=AsyncSession)
    policy_name = "db_error_policy"

    # Simulate a generic SQLAlchemyError (or any Exception) during execute
    mock_session.execute = AsyncMock(side_effect=Exception("Simulated DB error"))

    # Mock logger to check if error is logged
    mock_logger_error = mocker.patch("luthien_control.db.control_policy_crud.logger.error")

    with pytest.raises(LuthienDBOperationError, match="Unexpected error during policy config lookup"):
        await get_policy_config_by_name(mock_session, policy_name)

    mock_session.execute.assert_awaited_once()
    mock_logger_error.assert_called_once_with(
        f"Unexpected error fetching policy configuration by name '{policy_name}': Simulated DB error",
        exc_info=True,
    )


async def test_get_policy_config_by_name_sqlalchemy_error(mocker: MockerFixture):
    """Test SQLAlchemyError during get_policy_config_by_name."""
    mock_session = AsyncMock(spec=AsyncSession)
    policy_name = "sqlalchemy_error_policy"
    mock_session.execute = AsyncMock(side_effect=SQLAlchemyError("Simulated SQLAlchemy error"))

    # Mock logger to check if error is logged
    mock_logger_error = mocker.patch("luthien_control.db.control_policy_crud.logger.error")

    with pytest.raises(LuthienDBQueryError, match="Database query failed while fetching policy config"):
        await get_policy_config_by_name(mock_session, policy_name)

    mock_session.execute.assert_awaited_once()
    mock_logger_error.assert_called_once_with(
        f"SQLAlchemy error fetching policy configuration by name '{policy_name}': Simulated SQLAlchemy error",
        exc_info=True,
    )


async def test_save_policy_db_sqlalchemy_error(mocker: MockerFixture):
    """Test SQLAlchemyError during save_policy_to_db."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock(side_effect=SQLAlchemyError("Simulated SQLAlchemyError"))
    mock_session.rollback = AsyncMock()

    mock_logger_error = mocker.patch("luthien_control.db.control_policy_crud.logger.error")
    policy = ControlPolicy(name="sqlalchemy-error-policy", type="mock_type")

    with pytest.raises(LuthienDBTransactionError, match="Database transaction failed while creating policy"):
        await save_policy_to_db(mock_session, policy)

    mock_session.commit.assert_awaited_once()
    mock_session.rollback.assert_awaited_once()
    mock_logger_error.assert_called_once_with("SQLAlchemy error creating policy: Simulated SQLAlchemyError")


async def test_save_policy_db_generic_exception(mocker: MockerFixture):
    """Test generic Exception during save_policy_to_db."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.add = MagicMock()
    mock_session.commit = AsyncMock(side_effect=Exception("Simulated generic error"))
    mock_session.rollback = AsyncMock()

    mock_logger_error = mocker.patch("luthien_control.db.control_policy_crud.logger.error")
    policy = ControlPolicy(name="generic-error-policy", type="mock_type")

    with pytest.raises(LuthienDBOperationError, match="Unexpected error during policy creation"):
        await save_policy_to_db(mock_session, policy)

    mock_session.commit.assert_awaited_once()
    mock_session.rollback.assert_awaited_once()
    mock_logger_error.assert_called_once_with("Error creating policy: Simulated generic error")


async def test_get_policy_by_name_db_error(mocker: MockerFixture):
    """Test generic Exception during get_policy_by_name."""
    mock_session = AsyncMock(spec=AsyncSession)
    policy_name = "error_policy"
    mock_session.execute = AsyncMock(side_effect=Exception("Simulated DB error"))

    mock_logger_error = mocker.patch("luthien_control.db.control_policy_crud.logger.error")

    with pytest.raises(LuthienDBOperationError, match="Unexpected error during policy lookup"):
        await get_policy_by_name(mock_session, policy_name)

    mock_session.execute.assert_awaited_once()
    mock_logger_error.assert_called_once_with(
        f"Unexpected error fetching policy by name '{policy_name}': Simulated DB error",
        exc_info=True,
    )


async def test_get_policy_by_name_sqlalchemy_error(mocker: MockerFixture):
    """Test SQLAlchemyError during get_policy_by_name."""
    mock_session = AsyncMock(spec=AsyncSession)
    policy_name = "sqlalchemy_error_policy"
    mock_session.execute = AsyncMock(side_effect=SQLAlchemyError("Simulated SQLAlchemy error"))

    mock_logger_error = mocker.patch("luthien_control.db.control_policy_crud.logger.error")

    with pytest.raises(LuthienDBQueryError, match="Database query failed while fetching policy"):
        await get_policy_by_name(mock_session, policy_name)

    mock_session.execute.assert_awaited_once()
    mock_logger_error.assert_called_once_with(
        f"SQLAlchemy error fetching policy by name '{policy_name}': Simulated SQLAlchemy error",
        exc_info=True,
    )


async def test_list_policies_db_error(mocker: MockerFixture):
    """Test generic Exception during list_policies."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock(side_effect=Exception("Simulated DB error"))

    mock_logger_error = mocker.patch("luthien_control.db.control_policy_crud.logger.error")

    with pytest.raises(LuthienDBOperationError, match="Unexpected error during policy listing"):
        await list_policies(mock_session)

    mock_session.execute.assert_awaited_once()
    mock_logger_error.assert_called_once_with("Unexpected error listing policies: Simulated DB error")


async def test_list_policies_sqlalchemy_error(mocker: MockerFixture):
    """Test SQLAlchemyError during list_policies."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock(side_effect=SQLAlchemyError("Simulated SQLAlchemy error"))

    mock_logger_error = mocker.patch("luthien_control.db.control_policy_crud.logger.error")

    with pytest.raises(LuthienDBQueryError, match="Database query failed while listing policies"):
        await list_policies(mock_session)

    mock_session.execute.assert_awaited_once()
    mock_logger_error.assert_called_once_with("SQLAlchemy error listing policies: Simulated SQLAlchemy error")


async def test_update_policy_integrity_error(mocker: MockerFixture):
    """Test IntegrityError during update_policy commit."""
    mock_session = AsyncMock(spec=AsyncSession)
    existing_policy_mock = ControlPolicy(id=1, name="original-name", type="mock_type")
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing_policy_mock))
    )
    mock_session.commit = AsyncMock(side_effect=IntegrityError("commit failed", params=None, orig=None))  # type: ignore[arg-type]
    mock_session.rollback = AsyncMock()

    mock_logger_error = mocker.patch("luthien_control.db.control_policy_crud.logger.error")
    policy_update = ControlPolicy(name="new-name-violates-constraint")

    with pytest.raises(LuthienDBIntegrityError, match="Could not update policy due to constraint violation"):
        await update_policy(mock_session, 1, policy_update)

    mock_session.commit.assert_awaited_once()
    mock_session.rollback.assert_awaited_once()
    assert "Integrity error updating policy:" in mock_logger_error.call_args[0][0]


async def test_update_policy_sqlalchemy_error(mocker: MockerFixture):
    """Test SQLAlchemyError during update_policy commit."""
    mock_session = AsyncMock(spec=AsyncSession)
    existing_policy_mock = ControlPolicy(id=1, name="original-name", type="mock_type")
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing_policy_mock))
    )
    mock_session.commit = AsyncMock(side_effect=SQLAlchemyError("Simulated SQLAlchemyError on update"))
    mock_session.rollback = AsyncMock()

    mock_logger_error = mocker.patch("luthien_control.db.control_policy_crud.logger.error")
    policy_update = ControlPolicy(name="some-name")

    with pytest.raises(LuthienDBTransactionError, match="Database transaction failed while updating policy"):
        await update_policy(mock_session, 1, policy_update)

    mock_session.commit.assert_awaited_once()
    mock_session.rollback.assert_awaited_once()
    mock_logger_error.assert_called_once_with("SQLAlchemy error updating policy: Simulated SQLAlchemyError on update")


async def test_update_policy_generic_exception(mocker: MockerFixture):
    """Test generic Exception during update_policy commit."""
    mock_session = AsyncMock(spec=AsyncSession)
    existing_policy_mock = ControlPolicy(id=1, name="original-name", type="mock_type")
    mock_session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing_policy_mock))
    )
    mock_session.commit = AsyncMock(side_effect=Exception("Simulated generic error on update"))
    mock_session.rollback = AsyncMock()

    mock_logger_error = mocker.patch("luthien_control.db.control_policy_crud.logger.error")
    policy_update = ControlPolicy(name="some-name")

    with pytest.raises(LuthienDBOperationError, match="Unexpected error during policy update"):
        await update_policy(mock_session, 1, policy_update)

    mock_session.commit.assert_awaited_once()
    mock_session.rollback.assert_awaited_once()
    mock_logger_error.assert_called_once_with("Error updating policy: Simulated generic error on update")


async def test_load_policy_from_db_luthien_db_query_error_propagation(mocker: MockerFixture):
    """Test that LuthienDBQueryError from get_policy_by_name is propagated in load_policy_from_db."""
    mock_container = MagicMock()
    mock_session = AsyncMock()
    mock_container.db_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_container.db_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    policy_name = "test_policy_query_error_propagation"
    db_error = LuthienDBQueryError("Database query failed during policy lookup")

    mocker.patch(
        "luthien_control.db.control_policy_crud.get_policy_by_name",
        side_effect=db_error,
    )

    # LuthienDBQueryError should be propagated directly (line 215-216)
    with pytest.raises(LuthienDBQueryError, match="Database query failed during policy lookup"):
        await load_policy_from_db(policy_name, mock_container)


async def test_load_policy_from_db_non_policy_load_error_wrapped(mocker: MockerFixture):
    """Test that non-PolicyLoadError exceptions are wrapped in PolicyLoadError in load_policy_from_db."""
    mock_container = MagicMock()
    mock_session = AsyncMock()
    mock_container.db_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_container.db_session_factory.return_value.__aexit__ = AsyncMock(return_value=None)

    policy_name = "test_policy_non_policy_load_error"
    unexpected_error = RuntimeError("Some unexpected runtime error")

    mocker.patch(
        "luthien_control.db.control_policy_crud.get_policy_by_name",
        side_effect=unexpected_error,
    )

    mock_logger_exception = mocker.patch("luthien_control.db.control_policy_crud.logger.exception")

    error_msg = f"Unexpected error during loading process for '{policy_name}'"
    with pytest.raises(PolicyLoadError, match=error_msg) as exc_info:
        await load_policy_from_db(policy_name, mock_container)

    # Verify the original exception is preserved as the cause
    assert exc_info.value.__cause__ is unexpected_error

    mock_logger_exception.assert_called_once_with(
        f"Unexpected error during policy loading process for '{policy_name}': Some unexpected runtime error"
    )
