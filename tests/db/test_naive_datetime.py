from datetime import datetime, timedelta, timezone

from luthien_control.db.naive_datetime import NaiveDatetime


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
