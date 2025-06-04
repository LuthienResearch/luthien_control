from datetime import datetime, timedelta, timezone

from luthien_control.db.naive_datetime import NaiveDatetime
from luthien_control.db.sqlmodel_models import (
    ClientApiKey,
    ControlPolicy,
    LuthienLog,
)


def test_policy_creation():
    """Test successful creation of Policy with all fields, including inherited."""
    # Get the current time without timezone info, to match the model's behavior
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    data = {
        "id": 1,
        "name": "DbPolicy",
        # created_at and updated_at should be set by default factory
    }
    policy = ControlPolicy(**data)
    assert policy.id == 1
    assert policy.name == "DbPolicy"
    assert policy.is_active is True
    assert policy.config == {}
    assert isinstance(policy.created_at, datetime)
    assert isinstance(policy.updated_at, datetime)
    # Check that timestamps are recent (within a small delta)
    assert abs(policy.created_at - now) < timedelta(seconds=1)
    assert abs(policy.updated_at - now) < timedelta(seconds=1)
    assert policy.model_config.get("from_attributes") is True


def test_policy_creation_with_timestamps():
    """Test successful creation of Policy with explicit timestamps."""
    created = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    updated = datetime(2023, 1, 2, 13, 0, 0, tzinfo=timezone.utc)
    data = {
        "id": 2,
        "name": "ExplicitTimePolicy",
        "config": {"time_limit": 60},
        "is_active": False,
        "description": "Explicit time.",
        "created_at": created,
        "updated_at": updated,
    }
    policy = ControlPolicy(**data)
    assert policy.id == 2
    assert policy.name == "ExplicitTimePolicy"
    assert policy.is_active is False
    assert policy.config == {"time_limit": 60}
    assert policy.created_at == created
    assert policy.updated_at == updated


def test_control_policy_timestamp_validator():
    """Test that ControlPolicy.validate_timestamps updates updated_at."""
    initial_created_at = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None)
    initial_updated_at = datetime(2023, 1, 1, 12, 30, 0, tzinfo=timezone.utc).replace(tzinfo=None)

    policy_data = {
        "name": "ValidatorTestPolicy",
        "type": "TestType",
        "config": {},
        "created_at": initial_created_at,
        "updated_at": initial_updated_at,
    }

    # Create the initial policy instance
    policy1 = ControlPolicy(**policy_data)
    assert policy1.created_at == initial_created_at
    # On initial creation via __init__, if updated_at is provided, it's used.
    # The Pydantic v2 style @model_validator(mode='before') on get_validators
    # means validate_timestamps runs *before* __init__ field assignments if we use model_validate.
    # However, SQLModel models might behave slightly differently with direct __init__.
    # The current __init__ sets updated_at if not in data, otherwise uses data's value.
    # Let's verify this initial state.
    assert policy1.updated_at == initial_updated_at

    # Simulate a scenario where the model would be re-validated, e.g. by creating a new model from its dict
    # This should trigger the validator again.
    # For SQLModel, direct re-validation isn't as straightforward as Pydantic's model_validate.
    # The validator is a classmethod. We can call it directly to test its logic,
    # or see how it behaves when a model instance is created *through* SQLModel's mechanisms
    # that might invoke validators (like parsing from a dict that Pydantic part of SQLModel handles).

    # Let's test the validator's effect more directly if possible or by re-creating.
    # Option 1: Direct call to validator (if it were designed for that - it takes `values` dict)
    # validated_values = ControlPolicy.validate_timestamps(policy1.model_dump())
    # assert validated_values["updated_at"] > initial_updated_at
    # assert validated_values["created_at"] == initial_created_at

    # Option 2: Re-create the model instance, which should trigger validators
    # if SQLModel uses Pydantic's validation path.
    # Or, if creating from DB (from_attributes=True), validators might also run.
    # The `get_validators` suggests Pydantic v1 style validators.
    # Let's try re-creating from dict to see if validator runs as expected for Pydantic part of SQLModel
    # For SQLModel, model_validate is the Pydantic v2 way. For v1 style validators, they run during __init__ or parsing.

    # Given the @classmethod get_validators, and SQLModel's Pydantic integration,
    # when we create an instance, the validator *should* run.
    # The current __init__ in ControlPolicy explicitly sets created_at/updated_at if not present.
    # Then super().__init__ is called which would involve Pydantic validation and thus our validator.

    # Let's verify the behavior by creating another instance a bit later.
    # The first instance `policy1` already had its `updated_at` set.
    # If we dump it and create a new one, `created_at` should be preserved, `updated_at` should refresh.

    policy1_dict = policy1.model_dump()
    # Make sure some time passes for updated_at to change
    # This is tricky to test reliably without time mocking.
    # The validator sets updated_at = datetime.now().
    # The original created_at in policy1_dict is initial_created_at.

    # Re-create, this should trigger the validator which updates 'updated_at'
    policy2 = ControlPolicy.model_validate(policy1_dict)

    assert policy2.created_at == initial_created_at  # created_at should remain the same
    # updated_at should be newer than the original initial_updated_at for policy1, and policy1.updated_at
    # and also newer than policy1's updated_at if the validator ran.
    assert policy2.updated_at > initial_updated_at
    assert policy2.updated_at >= policy1.updated_at  # Should be at least same or newer
    # To be more robust, check it's close to now
    now_for_policy2 = datetime.now(timezone.utc).replace(tzinfo=None)
    assert abs(policy2.updated_at - now_for_policy2) < timedelta(seconds=1)


# --- Tests for ClientApiKey --- #


def test_client_api_key_creation_minimal():
    """Test successful creation of ClientApiKey with minimal fields."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    key = ClientApiKey(key_value="test_key_123", name="Test Key Minimal")

    assert key.id is None  # Default for primary key unless set
    assert key.key_value == "test_key_123"
    assert key.name == "Test Key Minimal"
    assert key.is_active is True  # Default value
    assert isinstance(key.created_at, datetime)
    assert abs(key.created_at - now) < timedelta(seconds=1)
    assert key.metadata_ is None  # Default value


def test_client_api_key_creation_all_fields():
    """Test successful creation of ClientApiKey with all fields specified."""
    created_time = datetime(2023, 5, 1, 10, 0, 0, tzinfo=timezone.utc).replace(tzinfo=None)
    metadata_content = {"owner": "test_user", "permissions": ["read"]}
    key = ClientApiKey(
        key_value="another_key_456",
        name="Full Test Key",
        is_active=False,
        created_at=created_time,  # Override default factory
        metadata_=metadata_content,
    )

    assert key.key_value == "another_key_456"
    assert key.name == "Full Test Key"
    assert key.is_active is False
    assert key.created_at == created_time
    assert key.metadata_ == metadata_content


# --- Tests for LuthienLog --- #


def test_luthien_log_creation_required_fields():
    """Test successful creation of LuthienLog with required fields."""
    now_utc = NaiveDatetime.now()
    log = LuthienLog(transaction_id="tx-abc-123", datatype="test_event")

    assert log.id is None
    assert log.transaction_id == "tx-abc-123"
    assert log.datatype == "test_event"
    assert isinstance(log.datetime, datetime)
    assert log.datetime.tzinfo is None  # Should be naive datetime
    assert abs((log.datetime - now_utc).total_seconds()) < 1
    assert log.data is None
    assert log.notes is None


def test_luthien_log_creation_all_fields():
    """Test successful creation of LuthienLog with all fields specified."""
    log_time = NaiveDatetime(2023, 6, 15, 14, 30, 0)
    log_data_content = {"event_details": "something happened"}
    log_notes_content = {"source": "test_suite"}

    log = LuthienLog(
        transaction_id="tx-xyz-789",
        datatype="full_info_event",
        datetime=log_time,  # Override default factory
        data=log_data_content,
        notes=log_notes_content,
        id=101,  # Explicitly set ID for testing if needed, though usually DB handles it
    )

    assert log.id == 101
    assert log.transaction_id == "tx-xyz-789"
    assert log.datatype == "full_info_event"
    assert log.datetime == log_time
    assert log.data == log_data_content
    assert log.notes == log_notes_content


def test_luthien_log_repr():
    """Test the __repr__ method of LuthienLog."""
    log_time = NaiveDatetime(2023, 1, 1, 0, 0, 0)
    log = LuthienLog(id=1, transaction_id="repr-tx", datetime=log_time, datatype="repr_test")
    # No timezone in repr
    expected_repr = "<LuthienLog(id=1, transaction_id='repr-tx', datetime='2023-01-01 00:00:00', datatype='repr_test')>"
    assert repr(log) == expected_repr


def test_luthien_log_with_timezone_aware_datetime():
    """Test that LuthienLog automatically converts timezone-aware datetimes to naive."""
    # This test demonstrates how our NaiveDatetime class prevents the original timezone issue
    timezone_aware_dt = datetime(2023, 6, 15, 14, 30, 0, tzinfo=timezone.utc)

    log = LuthienLog(
        transaction_id="tx-timezone-test",
        datatype="timezone_test_event",
        datetime=timezone_aware_dt,  # Pass timezone-aware datetime  # type: ignore[arg-type]
    )

    # The datetime should be automatically converted to naive
    assert log.datetime.tzinfo is None
    assert log.datetime.year == 2023
    assert log.datetime.month == 6
    assert log.datetime.day == 15
    assert log.datetime.hour == 14  # Should preserve the UTC time
