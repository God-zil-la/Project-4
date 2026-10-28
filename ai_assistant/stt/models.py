import uuid

from django.conf import settings
from django.db import models
from django.db.models import F, Q


class STTAccount(models.Model):
    # Separate mutex row: never write accounts, subscriptions or payment tables.
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    lock_version = models.PositiveBigIntegerField(default=0)


class STTPeriod(models.Model):
    account = models.ForeignKey(STTAccount, on_delete=models.CASCADE)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    # Opaque non-secret server verification reference, not a receipt/token.
    verification_ref = models.CharField(max_length=160)
    used_ms = models.PositiveBigIntegerField(default=0)
    reserved_ms = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['account', 'starts_at', 'ends_at'], name='stt_unique_period'),
            models.CheckConstraint(condition=Q(ends_at__gt=F('starts_at')), name='stt_valid_period'),
            models.CheckConstraint(condition=Q(used_ms__gte=0) & Q(reserved_ms__gte=0), name='stt_nonnegative_usage'),
        ]


class STTReservation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(STTAccount, on_delete=models.CASCADE)
    period = models.ForeignKey(STTPeriod, on_delete=models.CASCADE)
    request_id = models.UUIDField()
    audio_sha256 = models.CharField(max_length=64, null=True, blank=True)
    assistant_id = models.PositiveBigIntegerField(null=True, blank=True)
    duration_ms = models.PositiveBigIntegerField()
    # Frozen quota amount; measured duration remains the replay identity.
    charge_ms = models.PositiveBigIntegerField()
    state = models.CharField(max_length=12, default='reserved')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['account', 'request_id'], name='stt_idempotent_request'),
            models.CheckConstraint(condition=Q(charge_ms__gt=0), name='stt_positive_charge'),
            models.CheckConstraint(condition=Q(duration_ms__gt=0), name='stt_positive_duration'),
            models.CheckConstraint(condition=Q(state__in=['reserved', 'dispatched', 'uncertain', 'consumed', 'released']), name='stt_valid_state'),
        ]


class STTPeriodBinding(models.Model):
    """Immutable U6 identity binding; no provider payloads or purchase tokens."""
    identity = models.CharField(max_length=64, unique=True)
    period = models.OneToOneField(STTPeriod, on_delete=models.CASCADE)
    plan = models.CharField(max_length=20)
