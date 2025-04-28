from datetime import datetime, timezone

from luthien_control.db.sqlmodel_models import ControlPolicy


def test_policy_creation():
    """Test successful creation of Policy with all fields, including inherited."""
    # Get the current time without timezone info, to match the model's behavior
    datetime.now(timezone.utc).replace(tzinfo=None)
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
    datetime(2023, 1, 2, 13, 0, 0, tzinfo=timezone.utc)
    data = {
        "id": 2,
        "name": "ExplicitTimePolicy",
        "config": {"time_limit": 60},
        "is_active": False,
        "description": "Explicit time.",
    }
