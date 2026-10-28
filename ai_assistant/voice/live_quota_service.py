"""U6.3 Free Live Voice quota reservations."""

from uuid import UUID

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from ai_assistant.accounts.models import UserProfile

from .live_free_entitlement import (
    FreeVoiceAccessDenied,
    require_free_voice_access,
)
from .live_quota_models import (
    LiveVoiceMonthlyUsage,
    LiveVoiceQuotaReservation,
)
from .live_quota_policy import (
    FREE_MONTHLY_LIMIT_MS,
    free_monthly_period,
)


class LiveVoiceQuotaExceeded(Exception):
    pass


class LiveVoiceQuotaConflict(Exception):
    pass


def reserve_free_voice(*, user, request_id, duration_ms, observed_at=None):
    if user is None or not user.is_authenticated or not user.is_active:
        raise LiveVoiceQuotaConflict("active_authenticated_user_required")

    if type(duration_ms) is not int or duration_ms <= 0:
        raise LiveVoiceQuotaConflict("invalid_duration")

    try:
        request_uuid = UUID(str(request_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise LiveVoiceQuotaConflict("invalid_request_id") from exc

    with transaction.atomic():
        now = observed_at if observed_at is not None else timezone.now()
        try:
            UserProfile.objects.select_for_update().get(user_id=user.pk)
            require_free_voice_access(user=user)
        except (UserProfile.DoesNotExist, FreeVoiceAccessDenied) as exc:
            raise LiveVoiceQuotaConflict(
                "free_voice_entitlement_denied"
            ) from exc

        # Reject reuse of a request identity from an earlier period.
        # Same-period retries remain handled below.
        previous_period_request = (
            LiveVoiceQuotaReservation.objects.filter(
                usage__user_id=user.pk,
                request_id=request_uuid,
            ).exclude(usage__period_start=free_monthly_period(now)[0])
            .exists()
        )

        if previous_period_request:
            raise LiveVoiceQuotaConflict(
                "request_id_already_bound_to_another_period"
            )

        start, end = free_monthly_period(now)

        usage, _ = LiveVoiceMonthlyUsage.objects.get_or_create(
            user_id=user.pk,
            period_start=start,
            defaults={"period_end": end},
        )

        if usage.period_end != end:
            raise LiveVoiceQuotaConflict("period_conflict")

        existing = LiveVoiceQuotaReservation.objects.filter(
            usage=usage,
            request_id=request_uuid,
        ).first()

        if existing is not None:
            if existing.duration_ms != duration_ms:
                raise LiveVoiceQuotaConflict(
                    "request_duration_conflict"
                )
            if existing.state != "reserved":
                raise LiveVoiceQuotaConflict(
                    "reservation_not_active"
                )
            return existing

        updated = LiveVoiceMonthlyUsage.objects.annotate(
            total_ms=F("used_ms") + F("reserved_ms")
        ).filter(
            pk=usage.pk,
            total_ms__lte=FREE_MONTHLY_LIMIT_MS - duration_ms,
        ).update(
            reserved_ms=F("reserved_ms") + duration_ms,
        )

        if updated != 1:
            raise LiveVoiceQuotaExceeded(
                "monthly_free_voice_quota_exceeded"
            )

        return LiveVoiceQuotaReservation.objects.create(
            usage=usage,
            user_id=user.pk,
            request_id=request_uuid,
            duration_ms=duration_ms,
            state="reserved",
        )


def _finish_free_voice(*, user, request_id, target_state, consumed_ms=None, _settle_inactive=False):
    """Finalize a reservation exactly once.

    A committed reservation consumes its full reserved duration.
    A released reservation returns its full reserved duration.
    """
    if (
        user is None
        or not user.is_authenticated
        or (not user.is_active and not _settle_inactive)
    ):
        raise LiveVoiceQuotaConflict("active_authenticated_user_required")

    try:
        request_uuid = UUID(str(request_id))
    except (ValueError, TypeError, AttributeError) as exc:
        raise LiveVoiceQuotaConflict("invalid_request_id") from exc

    if target_state not in {"committed", "released"}:
        raise LiveVoiceQuotaConflict("invalid_target_state")

    with transaction.atomic():
        reservations = (
            LiveVoiceQuotaReservation.objects
            .select_for_update()
            .select_related("usage")
            .filter(
                usage__user_id=user.pk,
                request_id=request_uuid,
            )
        )

        reservation = reservations.first()

        if reservation is None:
            raise LiveVoiceQuotaConflict("reservation_not_found")

        if target_state == "committed":
            requested_charge = (
                reservation.duration_ms
                if consumed_ms is None
                else consumed_ms
            )
            if (
                type(requested_charge) is not int
                or requested_charge < 0
                or requested_charge > reservation.duration_ms
            ):
                raise LiveVoiceQuotaConflict("invalid_consumed_duration")

        if reservation.state == target_state:
            if (
                target_state == "committed"
                and reservation.charged_ms != requested_charge
            ):
                raise LiveVoiceQuotaConflict("conflicting_committed_charge")
            return reservation

        if reservation.state != "reserved":
            raise LiveVoiceQuotaConflict(
                "reservation_already_finalized"
            )

        usage = LiveVoiceMonthlyUsage.objects.select_for_update().get(
            pk=reservation.usage_id,
            user_id=user.pk,
        )

        if usage.reserved_ms < reservation.duration_ms:
            raise LiveVoiceQuotaConflict(
                "reserved_balance_mismatch"
            )

        if target_state == "committed":
            charge_ms = (
                reservation.duration_ms
                if consumed_ms is None
                else consumed_ms
            )
            if (
                type(charge_ms) is not int
                or charge_ms < 0
                or charge_ms > reservation.duration_ms
            ):
                raise LiveVoiceQuotaConflict(
                    "invalid_consumed_duration"
                )
            usage.used_ms = F("used_ms") + charge_ms

        usage.reserved_ms = F("reserved_ms") - reservation.duration_ms
        usage.save(
            update_fields=(
                ["used_ms", "reserved_ms"]
                if target_state == "committed"
                else ["reserved_ms"]
            )
        )

        reservation.state = target_state
        if target_state == "committed":
            reservation.charged_ms = charge_ms
            reservation.save(update_fields=["state", "charged_ms"])
        else:
            reservation.save(update_fields=["state"])
        reservation.refresh_from_db()

        return reservation


def commit_free_voice(*, user, request_id, consumed_ms=None):
    """Consume actual duration, capped by the reservation."""
    return _finish_free_voice(
        user=user,
        request_id=request_id,
        target_state="committed",
        consumed_ms=consumed_ms,
    )


def release_free_voice(*, user, request_id):
    """Return a previously reserved Free Live Voice duration."""
    return _finish_free_voice(
        user=user,
        request_id=request_id,
        target_state="released",
    )




def _settle_session_free_voice(*, user, request_id, consumed_ms):
    """Server-only settlement survives account deactivation; grants no new use."""
    return _finish_free_voice(user=user, request_id=request_id,
        target_state="committed", consumed_ms=consumed_ms, _settle_inactive=True)
