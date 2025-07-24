from datetime import datetime, timezone, tzinfo
from typing import Any, Optional

from pydantic_core import core_schema


class NaiveDatetime(datetime):
    """A datetime that automatically strips timezone info."""

    def __new__(cls, *args, **kwargs):
        # Handle datetime object as first argument
        if args and isinstance(args[0], datetime):
            dt = args[0]
            # Convert to naive UTC if timezone-aware, otherwise keep as-is
            if dt.tzinfo is not None:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return super().__new__(cls, dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second, dt.microsecond)
        else:
            # Normal datetime constructor
            return super().__new__(cls, *args, **kwargs)

    @classmethod
    def now(cls, tz: Optional[tzinfo] = None) -> "NaiveDatetime":
        """Create a NaiveDatetime representing the current UTC time (naive)."""
        # Always return naive UTC time regardless of tz parameter for consistency
        return cls(datetime.now(timezone.utc))

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> core_schema.CoreSchema:
        """Pydantic schema for NaiveDatetime."""
        return core_schema.with_info_before_validator_function(
            cls._convert_to_naive,
            core_schema.datetime_schema(),
        )

    @classmethod
    def _convert_to_naive(cls, value: Any, info: Any) -> Any:
        """Convert datetime to naive before Pydantic processes it."""
        if isinstance(value, datetime):
            return cls(value)  # This will trigger our __new__ method
        return value  # Let Pydantic handle other types
