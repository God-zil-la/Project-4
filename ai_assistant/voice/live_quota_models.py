"""U6.3 Live Voice monthly quota storage."""

from django.conf import settings
from django.db import models


class LiveVoiceMonthlyUsage(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    period_start = models.DateTimeField()
    period_end = models.DateTimeField()
    used_ms = models.PositiveBigIntegerField(default=0)
    reserved_ms = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "period_start"],
                name="u63_unique_monthly_usage",
            ),
        ]


class LiveVoiceQuotaReservation(models.Model):
    usage = models.ForeignKey(
        LiveVoiceMonthlyUsage,
        on_delete=models.CASCADE,
    )
    request_id = models.UUIDField()
    duration_ms = models.PositiveBigIntegerField()
    charged_ms = models.PositiveBigIntegerField(null=True, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    state = models.CharField(max_length=16, default="reserved")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["usage", "request_id"],
                name="u63_unique_quota_request",
            ),
            models.UniqueConstraint(
                fields=["user", "request_id"],
                name="u63_unique_user_request",
            ),
        ]
