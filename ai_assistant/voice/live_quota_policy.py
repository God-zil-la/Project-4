"""U6.3 Live Voice quota policy. No external API calls."""

from calendar import monthrange
from datetime import datetime, timezone

FREE_MONTHLY_LIMIT_MS = 600_000


def free_monthly_period(now):
    """Return the current UTC calendar-month interval."""
    if not isinstance(now, datetime):
        raise TypeError("datetime_required")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("timezone_aware_datetime_required")

    now = now.astimezone(timezone.utc)

    start = datetime(
        now.year, now.month, 1, tzinfo=timezone.utc
    )

    if now.month == 12:
        end = datetime(
            now.year + 1, 1, 1, tzinfo=timezone.utc
        )
    else:
        end = datetime(
            now.year, now.month + 1, 1, tzinfo=timezone.utc
        )

    return start, end


def remaining_free_ms(*, used_ms, reserved_ms):
    """Return remaining Free Live Voice time in milliseconds."""
    for value in (used_ms, reserved_ms):
        if type(value) is not int or value < 0:
            raise ValueError("invalid_usage_value")

    return max(
        0,
        FREE_MONTHLY_LIMIT_MS - used_ms - reserved_ms,
    )


def can_reserve_free(*, used_ms, reserved_ms, duration_ms):
    """Check whether a new recording fits within the Free quota."""
    if type(duration_ms) is not int or duration_ms <= 0:
        raise ValueError("invalid_duration")

    return duration_ms <= remaining_free_ms(
        used_ms=used_ms,
        reserved_ms=reserved_ms,
    )
