from datetime import datetime, timedelta, timezone
from typing import Any

from luthien_control.db.naive_datetime import NaiveDatetime
from pydantic import BaseModel


def test_naive_datetime_strips_timezone():
    """Test that NaiveDatetime automatically strips timezone info."""
    # Test with timezone-aware datetime
    aware_dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    naive_dt = NaiveDatetime(aware_dt)

    assert naive_dt.tzinfo is None
    assert naive_dt.year == 2023
    assert naive_dt.month == 1
    assert naive_dt.day == 1
    assert naive_dt.hour == 12


def test_naive_datetime_preserves_naive():
    """Test that NaiveDatetime preserves already-naive datetimes."""
    # Test with already-naive datetime
    original_naive = datetime(2023, 1, 1, 12, 0, 0)
    naive_dt = NaiveDatetime(original_naive)

    assert naive_dt.tzinfo is None
    assert naive_dt == original_naive


def test_naive_datetime_converts_non_utc_timezone():
    """Test that NaiveDatetime converts non-UTC timezones to naive UTC."""
    # Create a timezone-aware datetime in EST (UTC-5)
    est = timezone(timedelta(hours=-5))
    est_dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=est)  # 12 PM EST = 5 PM UTC

    naive_dt = NaiveDatetime(est_dt)

    assert naive_dt.tzinfo is None
    assert naive_dt.hour == 17  # Should be converted to 5 PM UTC


def test_naive_datetime_normal_constructor():
    """Test that NaiveDatetime works with normal datetime constructor arguments."""
    naive_dt = NaiveDatetime(2023, 1, 1, 12, 0, 0)

    assert naive_dt.tzinfo is None
    assert naive_dt.year == 2023
    assert naive_dt.month == 1
    assert naive_dt.day == 1
    assert naive_dt.hour == 12


def test_naive_datetime_now():
    """Test that NaiveDatetime.now() returns current naive UTC time."""
    before = NaiveDatetime.now()
    naive_now = NaiveDatetime.now()
    after = NaiveDatetime.now()

    # Should be naive
    assert naive_now.tzinfo is None

    # Should be close to current time (within 1 second)
    assert before <= naive_now <= after or abs((naive_now - before).total_seconds()) < 1
    assert isinstance(naive_now, NaiveDatetime)


def test_tx_logging_policy_datetime_handling():
    """Test that demonstrates our solution prevents the original timezone issue."""
    # Simulate what TxLoggingPolicy does now - creates timezone-aware datetime
    # but converts it to naive before passing to LuthienLog
    timezone_aware_dt = datetime.now(timezone.utc)

    # Our fix: use NaiveDatetime constructor to strip timezone
    naive_dt = NaiveDatetime(timezone_aware_dt)

    # Verify it's properly converted
    assert naive_dt.tzinfo is None
    assert isinstance(naive_dt, NaiveDatetime)


def test_pydantic_core_schema():
    """Test the Pydantic core schema generation."""
    schema = NaiveDatetime.__get_pydantic_core_schema__(Any, lambda x: x)
    assert isinstance(schema, dict)
    assert "type" in schema


def test_pydantic_convert_to_naive_with_datetime():
    """Test the _convert_to_naive method with datetime input."""
    aware_dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    result = NaiveDatetime._convert_to_naive(aware_dt, None)

    assert isinstance(result, NaiveDatetime)
    assert result.tzinfo is None


def test_pydantic_convert_to_naive_with_non_datetime():
    """Test the _convert_to_naive method with non-datetime input."""
    # Test with string - should pass through unchanged
    string_value = "2023-01-01T12:00:00"
    result = NaiveDatetime._convert_to_naive(string_value, None)
    assert result == string_value

    # Test with integer - should pass through unchanged
    int_value = 12345
    result = NaiveDatetime._convert_to_naive(int_value, None)
    assert result == int_value


def test_pydantic_integration():
    """Test NaiveDatetime integration with Pydantic models."""

    class TestModel(BaseModel):
        dt: NaiveDatetime

    # Test with timezone-aware datetime
    aware_dt = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    model = TestModel(dt=aware_dt)  # type: ignore[arg-type]

    assert isinstance(model.dt, NaiveDatetime)
    assert model.dt.tzinfo is None

    # Test with naive datetime
    naive_dt = datetime(2023, 1, 1, 12, 0, 0)
    model2 = TestModel(dt=naive_dt)  # type: ignore[arg-type]

    assert isinstance(model2.dt, NaiveDatetime)
    assert model2.dt.tzinfo is None
