from datetime import date
import secrets

from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """Extended profile model linked to Django's User."""

    PLAN_FREE = "free"
    PLAN_PREMIUM = "premium"
    PLAN_PRO = "pro"

    PLAN_CHOICES = [
        (PLAN_FREE, "Free"),
        (PLAN_PREMIUM, "Premium"),
        (PLAN_PRO, "Pro"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )

    plan = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
        default=PLAN_FREE,
    )

    # Kept for backwards compatibility while the
    # subscription system is being migrated to plans.
    is_subscribed = models.BooleanField(default=False)

    stripe_customer_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    stripe_subscription_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )

    stripe_subscription_status = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )

    subscription_current_period_end = models.DateTimeField(
        blank=True,
        null=True,
    )

    daily_message_count = models.IntegerField(default=0)
    last_reset = models.DateField(default=date.today)

    api_key = models.CharField(
        max_length=64,
        unique=True,
        blank=True,
    )

    @property
    def has_paid_plan(self):
        """Return True for Premium or Pro users."""
        return self.plan in {
            self.PLAN_PREMIUM,
            self.PLAN_PRO,
        }

    @property
    def is_premium(self):
        return self.plan == self.PLAN_PREMIUM

    @property
    def is_pro(self):
        return self.plan == self.PLAN_PRO

    def reset_daily_count(self):
        """Reset only an outdated database row, never a stale instance's counter."""
        today = date.today()
        type(self).objects.filter(pk=self.pk).exclude(last_reset=today).update(
            daily_message_count=0, last_reset=today,
        )
        self.refresh_from_db(fields=["daily_message_count", "last_reset"])

    def increment_message_count(self):
        """Increment atomically, including requests that complete after midnight."""
        today = date.today()
        type(self).objects.filter(pk=self.pk).update(
            daily_message_count=models.Case(
                models.When(last_reset=today, then=models.F("daily_message_count") + 1),
                default=models.Value(1), output_field=models.IntegerField(),
            ),
            last_reset=today,
        )
        self.refresh_from_db(fields=["daily_message_count", "last_reset"])

    def generate_api_key(self):
        """Generate and save a new API key for the user."""
        self.api_key = secrets.token_hex(32)
        self.save(
            update_fields=["api_key"]
        )

    def __str__(self):
        return f"{self.user.username} Profile"