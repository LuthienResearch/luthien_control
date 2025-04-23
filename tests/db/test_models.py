from datetime import datetime, timedelta, timezone

from luthien_control.db.sqlmodel_models import ControlPolicy


def test_policy_creation():
    """Test successful creation of Policy with all fields, including inherited."""
    # Get the current time without timezone info, to match the model's behavior
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    data = {
        "id": 1,
        "name": "DbPolicy",
        "policy_class_path": "luthien_control.policies.db_policy.DbPolicy",
        # created_at and updated_at should be set by default factory
    }
    policy = ControlPolicy(**data)
    assert policy.id == 1
    assert policy.name == "DbPolicy"
    assert policy.policy_class_path == "luthien_control.policies.db_policy.DbPolicy"
    assert policy.is_active is True
    assert policy.config is None
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
        "policy_class_path": "luthien_control.policies.time_policy.TimePolicy",
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
