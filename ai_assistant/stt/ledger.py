"""Internal STT accounting. No endpoint, billing adapters or provider calls.

VerifiedPeriod is a trusted server-only boundary, NOT proof of verification.
Only a future authoritative adapter may construct it; never deserialize it from
request data. Caller must verify identity, current plan and period on every reserve.
"""
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
import time
from uuid import UUID

from django.db import OperationalError, connection, transaction
from django.db.models import F
from django.utils import timezone

from .models import STTAccount, STTPeriod, STTReservation
from .policy import stt_limit_ms


class LedgerError(Exception):
    pass


class QuotaExceeded(LedgerError):
    pass


class Conflict(LedgerError):
    pass


class InvalidPeriod(LedgerError):
    pass


@dataclass(frozen=True)
class VerifiedPeriod:
    user_id: int
    plan: str
    starts_at: datetime
    ends_at: datetime
    verification_ref: str


def _atomic_operation(function):
    @wraps(function)
    def call(*args, **kwargs):
        # SQLite retries restart the ENTIRE local transaction, never HTTP work.
        # PostgreSQL uses the same account row lock and does not need this retry.
        nested = connection.in_atomic_block
        for attempt in range(6):
            try:
                with transaction.atomic():
                    return function(*args, **kwargs)
            except OperationalError as exc:
                if (nested or connection.vendor != 'sqlite' or attempt == 5
                        or 'locked' not in str(exc).lower()):
                    raise
                time.sleep(0.01 * (attempt + 1))
    return call


def _lock_account(user_id):
    STTAccount.objects.get_or_create(user_id=user_id)
    # UPDATE is a row lock on PostgreSQL and a write lock on SQLite. Acquiring
    # it before ledger reads also protects initial period creation and overlap.
    STTAccount.objects.filter(user_id=user_id).update(lock_version=F('lock_version') + 1)
    return STTAccount.objects.get(user_id=user_id)


def _validate(period):
    if not isinstance(period, VerifiedPeriod):
        raise InvalidPeriod('server_verified_period_required')
    if (not isinstance(period.starts_at, datetime) or not isinstance(period.ends_at, datetime)
            or timezone.is_naive(period.starts_at) or timezone.is_naive(period.ends_at)
            or not period.starts_at <= timezone.now() < period.ends_at
            or not isinstance(period.verification_ref, str)
            or not period.verification_ref.strip() or len(period.verification_ref) > 160):
        raise InvalidPeriod('invalid_or_inactive_period')
    limit = stt_limit_ms(period.plan)
    if not limit:
        raise LedgerError('plan_not_enabled')
    return limit


@_atomic_operation
def reserve(*, period, request_id, duration_ms, audio_sha256, assistant_id):
    """Reserve each started minute; preserve measured duration for replay checks.

    Reusing a key with changed duration/period fails even after final settlement.
    A plan upgrade changes the ceiling, never clears usage. Downgrades preserve
    usage and prevent new reservations when the lower ceiling is exceeded.
    """
    if (not isinstance(audio_sha256, str)
            or len(audio_sha256) != 64
            or any(c not in '0123456789abcdef' for c in audio_sha256)
            or type(assistant_id) is not int
            or assistant_id <= 0):
        raise LedgerError('invalid_audio_identity')
    limit = _validate(period)
    if type(duration_ms) is not int or duration_ms <= 0 or duration_ms > limit:
        raise QuotaExceeded('invalid_duration_or_quota_exceeded')
    try:
        key = UUID(str(request_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise LedgerError('invalid_request_id') from exc
    account = _lock_account(period.user_id)
    # Check time again after waiting for a concurrent transaction's lock.
    limit = _validate(period)
    existing = STTReservation.objects.filter(account=account, request_id=key).select_related('period').first()
    if existing:
        if (existing.audio_sha256 != audio_sha256
                or existing.assistant_id != assistant_id
                or existing.duration_ms != duration_ms
                or existing.period.starts_at != period.starts_at
                or existing.period.ends_at != period.ends_at
                or existing.period.verification_ref != period.verification_ref):
            raise Conflict('idempotency_key_reused')
        return existing
    bucket = STTPeriod.objects.filter(account=account, starts_at=period.starts_at, ends_at=period.ends_at).first()
    if bucket is None:
        if STTPeriod.objects.filter(account=account, starts_at__lt=period.ends_at, ends_at__gt=period.starts_at).exists():
            raise InvalidPeriod('overlapping_period_requires_reconciliation')
        bucket = STTPeriod.objects.create(account=account, starts_at=period.starts_at,
                                         ends_at=period.ends_at, verification_ref=period.verification_ref)
    elif bucket.verification_ref != period.verification_ref:
        raise InvalidPeriod('period_verification_changed')
    # Freeze the charge once, using integer ceiling per request, not per period.
    charge_ms = ((duration_ms + 59_999) // 60_000) * 60_000
    # Atomic conditional update is an additional guard, beyond account locking.
    changed = STTPeriod.objects.filter(pk=bucket.pk, used_ms__lte=limit - charge_ms - F('reserved_ms')).update(
        reserved_ms=F('reserved_ms') + charge_ms)
    if not changed:
        raise QuotaExceeded('stt_quota_exceeded')
    return STTReservation.objects.create(
        account=account, period=bucket, request_id=key,
        duration_ms=duration_ms, charge_ms=charge_ms,
        audio_sha256=audio_sha256, assistant_id=assistant_id)


def _locked_reservation(user_id, reservation_id):
    # No object is returned across account boundaries.
    account = _lock_account(user_id)
    try:
        return STTReservation.objects.get(pk=reservation_id, account=account)
    except STTReservation.DoesNotExist as exc:
        raise LedgerError('reservation_not_found') from exc


@_atomic_operation
def claim_dispatch(*, user_id, reservation_id, period=None):
    """Only the caller receiving True may send ONE external request.

    Commit this operation before network I/O. A crash after claim is ambiguous:
    do not redispatch or refund automatically. No HTTP request occurs here.
    """
    if connection.savepoint_ids:
        raise LedgerError('dispatch_claim_requires_outermost_transaction')
    row = _locked_reservation(user_id, reservation_id)
    if row.state != 'reserved':
        return False
    bucket = row.period
    if not bucket.starts_at <= timezone.now() < bucket.ends_at:
        raise InvalidPeriod('dispatch_period_expired_or_inactive')
    if period is not None:
        _validate(period)
        if (period.user_id != user_id or period.starts_at != bucket.starts_at
                or period.ends_at != bucket.ends_at
                or period.verification_ref != bucket.verification_ref):
            raise InvalidPeriod('dispatch_period_mismatch')
    row.state = 'dispatched'
    row.save(update_fields=['state', 'updated_at'])
    return True


@_atomic_operation
def settle(*, user_id, reservation_id, outcome):
    """success consumes the frozen reserved charge; not_processed releases the hold.

    not_processed after dispatch requires authoritative evidence of rejection or
    non-processing. HTTP errors alone do NOT establish that. uncertain retains
    the hold. Repeated identical terminal settlements have no financial effect;
    contradictory terminal settlements are rejected.
    """
    if outcome not in {'success', 'not_processed', 'uncertain'}:
        raise LedgerError('invalid_outcome')
    row = _locked_reservation(user_id, reservation_id)
    target = {'success': 'consumed', 'not_processed': 'released', 'uncertain': 'uncertain'}[outcome]
    if row.state in {'consumed', 'released'}:
        if row.state != target:
            raise Conflict('reservation_already_finalized')
        return row
    if row.state == 'reserved' and outcome != 'not_processed':
        raise Conflict('request_not_dispatched')
    if outcome == 'uncertain':
        row.state = target
        row.save(update_fields=['state', 'updated_at'])
        return row
    changes = {'reserved_ms': F('reserved_ms') - row.charge_ms}
    if outcome == 'success':
        changes['used_ms'] = F('used_ms') + row.charge_ms
    if not STTPeriod.objects.filter(pk=row.period_id, account=row.account,
                                   reserved_ms__gte=row.charge_ms).update(**changes):
        raise Conflict('ledger_invariant_failed')
    row.state = target
    row.save(update_fields=['state', 'updated_at'])
    return row
