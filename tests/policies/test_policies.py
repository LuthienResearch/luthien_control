"""Test the policies module initialization."""

from luthien_control.policies import ControlPolicy, NoopPolicy, PolicyManager


def test_policy_imports():
    """Test that policy classes are properly imported."""
    assert isinstance(PolicyManager(), PolicyManager)
    assert issubclass(NoopPolicy, ControlPolicy)
    # This verifies the __all__ list is working correctly
    from luthien_control.policies import __all__

    assert set(__all__) == {"PolicyManager", "ControlPolicy", "NoopPolicy"}
