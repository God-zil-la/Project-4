"""U6.3 server-authoritative Free Live Voice timer primitives.

Not connected to HTTP endpoints or external AI providers.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone

from django.utils import timezone

from .live_quota_policy import FREE_MONTHLY_LIMIT_MS


class LiveSessionTimerError(Exception):
    pass


@dataclass(frozen=True)
class TimerSnapshot:
    started_at: datetime
    deadline_at: datetime
    observed_at: datetime
    elapsed_ms: int
    chargeable_ms: int
    remaining_ms: int
    expired: bool


def _utc(value):
    if not isinstance(value, datetime):
        raise LiveSessionTimerError("invalid_timestamp")
    if timezone.is_naive(value):
        raise LiveSessionTimerError("naive_timestamp")
    return value.astimezone(dt_timezone.utc)


def _milliseconds(delta):
    return max(
        0,
        delta.days * 86400000
        + delta.seconds * 1000
        + delta.microseconds // 1000,
    )


def timer_snapshot(
    *,
    started_at,
    reserved_ms,
    observed_at=None,
    monthly_period_end=None,
):
    """Calculate elapsed time using trusted server timestamps."""
    if (
        type(reserved_ms) is not int
        or reserved_ms <= 0
        or reserved_ms > FREE_MONTHLY_LIMIT_MS
    ):
        raise LiveSessionTimerError("invalid_reservation")

    start = _utc(started_at)
    now = _utc(observed_at if observed_at is not None else timezone.now())

    if now < start:
        raise LiveSessionTimerError("clock_before_start")

    deadline = start + timedelta(milliseconds=reserved_ms)

    if monthly_period_end is not None:
        period_end = _utc(monthly_period_end)
        if period_end <= start:
            raise LiveSessionTimerError("invalid_period")
        deadline = min(deadline, period_end)

    elapsed = _milliseconds(now - start)
    chargeable = _milliseconds(min(now, deadline) - start)
    remaining = _milliseconds(deadline - min(now, deadline))

    return TimerSnapshot(
        started_at=start,
        deadline_at=deadline,
        observed_at=now,
        elapsed_ms=elapsed,
        chargeable_ms=chargeable,
        remaining_ms=remaining,
        expired=now >= deadline,
    )


def finalized_charge(
    *,
    started_at,
    reserved_ms,
    ended_at,
    monthly_period_end=None,
):
    """Return elapsed charge capped by reservation and UTC period."""
    return timer_snapshot(
        started_at=started_at,
        reserved_ms=reserved_ms,
        observed_at=ended_at,
        monthly_period_end=monthly_period_end,
    ).chargeable_ms