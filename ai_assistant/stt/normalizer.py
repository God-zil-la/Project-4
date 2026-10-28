"""U6-only normalization of ALREADY verified server evidence; no network I/O.

This internal typed boundary is not a signature verifier. Never construct its
input from public request fields. A future trusted adapter must establish owner,
provider, environment, stable subscription/cycle identity and current entitlement.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone as utc_timezone
from hashlib import sha256
import json

from django.utils import timezone

from . import ledger
from .models import STTPeriodBinding


@dataclass(frozen=True)
class ServerPeriodEvidence:
    user_id: int
    provider: str
    environment: str
    subscription_id: str
    cycle_id: str
    plan: str
    starts_at: datetime
    ends_at: datetime
    verified_at: datetime
    entitlement_active: bool
    verification_succeeded: bool
    # Explicitly approved ordinary monthly period only; no inference from dates.
    category: str
    metadata: dict = field(default_factory=dict)


def _utc(value):
    if (not isinstance(value, datetime) or timezone.is_naive(value)
            or value.utcoffset() != timedelta(0)):
        raise ledger.InvalidPeriod('explicit_utc_required')
    return value.astimezone(utc_timezone.utc)


def normalize(evidence):
    """Pure normalizer. DB consistency is enforced by reserve_normalized below."""
    if not isinstance(evidence, ServerPeriodEvidence):
        raise ledger.InvalidPeriod('typed_server_evidence_required')
    if (evidence.verification_succeeded is not True or evidence.entitlement_active is not True
            or type(evidence.user_id) is not int or evidence.user_id <= 0):
        raise ledger.InvalidPeriod('verified_active_owner_required')
    if (evidence.provider not in {'stripe', 'apple', 'google'}
            or evidence.environment not in {'production', 'sandbox'}
            or evidence.category != 'ordinary_monthly'
            or evidence.plan not in {'premium', 'pro'}):
        raise ledger.InvalidPeriod('unsupported_or_undecided_policy')
    for identifier in (evidence.subscription_id, evidence.cycle_id):
        if (not isinstance(identifier, str) or not identifier or identifier != identifier.strip()
                or len(identifier) > 256):
            raise ledger.InvalidPeriod('stable_identity_required')
    start, end, verified = map(_utc, (evidence.starts_at, evidence.ends_at, evidence.verified_at))
    now = timezone.now()
    if not start <= verified <= now < end:
        raise ledger.InvalidPeriod('inactive_or_contradictory_period')
    identity = sha256(json.dumps([
        evidence.user_id, evidence.provider, evidence.environment,
        evidence.subscription_id, evidence.cycle_id,
    ], separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
    # Neither dates, plan, verification time nor mutable metadata create identity.
    return ledger.VerifiedPeriod(evidence.user_id, evidence.plan, start, end, 'u6:' + identity)


def _check_binding(binding, period):
    stored = binding.period
    if (stored.account.user_id != period.user_id or stored.starts_at != period.starts_at
            or stored.ends_at != period.ends_at or stored.verification_ref != period.verification_ref):
        raise ledger.InvalidPeriod('stable_cycle_has_conflicting_period')
    if binding.plan != period.plan:
        raise ledger.InvalidPeriod('plan_change_policy_not_approved')


@ledger._atomic_operation
def reserve_normalized(*, evidence, request_id, duration_ms, audio_sha256, assistant_id):
    period = normalize(evidence)
    ledger._lock_account(period.user_id)
    period = normalize(evidence)  # Recheck time after lock wait.
    identity = period.verification_ref[3:]
    binding = STTPeriodBinding.objects.filter(identity=identity).select_related('period__account').first()
    if binding:
        _check_binding(binding, period)
    row = ledger.reserve(
        period=period, request_id=request_id, duration_ms=duration_ms,
        audio_sha256=audio_sha256, assistant_id=assistant_id)
    if binding is None:
        STTPeriodBinding.objects.create(identity=identity, period=row.period, plan=period.plan)
    return row


def claim_normalized(*, evidence, reservation_id):
    """Recheck trusted evidence; ledger checks period again under the account lock.

    Binding fields are immutable through this API. No network I/O or automatic
    rollover/refund occurs. Caller still needs fresh authoritative entitlement
    evidence at dispatch; this module cannot discover revocation by itself.
    """
    period = normalize(evidence)
    binding = STTPeriodBinding.objects.filter(identity=period.verification_ref[3:]).select_related('period__account').first()
    if binding is None:
        raise ledger.InvalidPeriod('period_not_reserved')
    _check_binding(binding, period)
    return ledger.claim_dispatch(user_id=period.user_id, reservation_id=reservation_id, period=period)
