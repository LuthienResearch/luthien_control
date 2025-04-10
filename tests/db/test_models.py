from datetime import datetime, timedelta, timezone

import pytest
from luthien_control.db.models import Policy, PolicyBase
from pydantic import ValidationError


def test_policy_base_creation():
    """Test successful creation of PolicyBase with minimal required data."""
    data = {
        "name": "TestPolicy",
        "policy_class_path": "luthien_control.policies.some_policy.SomePolicy",
    }
    policy_base = PolicyBase(**data)
    assert policy_base.name == "TestPolicy"
    assert policy_base.policy_class_path == "luthien_control.policies.some_policy.SomePolicy"
    assert policy_base.is_active is True  # Check default
    assert policy_base.config is None  # Check default
    assert policy_base.description is None  # Check default


def test_policy_base_full_data():
    """Test successful creation of PolicyBase with all fields provided."""
    data = {
        "name": "FullPolicy",
        "policy_class_path": "luthien_control.policies.another.AnotherPolicy",
        "config": {"key": "value", "timeout": 30},
        "is_active": False,
        "description": "A test policy description.",
    }
    policy_base = PolicyBase(**data)
    assert policy_base.name == "FullPolicy"
    assert policy_base.policy_class_path == "luthien_control.policies.another.AnotherPolicy"
    assert policy_base.is_active is False
    assert policy_base.config == {"key": "value", "timeout": 30}
    assert policy_base.description == "A test policy description."


def test_policy_base_missing_required_fields():
    """Test that ValidationError is raised if required fields are missing."""
    with pytest.raises(ValidationError, match="name"):
        PolicyBase(policy_class_path="path.to.Class")

    with pytest.raises(ValidationError, match="policy_class_path"):
        PolicyBase(name="TestName")


def test_policy_base_invalid_types():
    """Test that ValidationError is raised for invalid field types."""
    with pytest.raises(ValidationError, match="is_active"):
        PolicyBase(
            name="TypeTest",
            policy_class_path="path.to.Class",
            is_active="not_a_boolean",
        )

    with pytest.raises(ValidationError, match="config"):
        PolicyBase(
            name="TypeTest",
            policy_class_path="path.to.Class",
            config="not_a_dict_or_none",
        )


def test_policy_creation():
    """Test successful creation of Policy, inheriting from PolicyBase."""
    now = datetime.now(timezone.utc)
    data = {
        "id": 1,
        "name": "DbPolicy",
        "policy_class_path": "luthien_control.policies.db_policy.DbPolicy",
        # created_at and updated_at should be set by default factory
    }
    policy = Policy(**data)
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
    policy = Policy(**data)
    assert policy.id == 2
    assert policy.name == "ExplicitTimePolicy"
    assert policy.is_active is False
    assert policy.config == {"time_limit": 60}
    assert policy.created_at == created
    assert policy.updated_at == updated
