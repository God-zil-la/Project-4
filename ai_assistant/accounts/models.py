import secrets

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


def current_month_start():
    """Return the first day of the current calendar month."""
    today = timezone.localdate()
    return today.replace(day=1)


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

    subscription_cancel_at_period_end = models.BooleanField(
        default=False
    )

    subscription_ends_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    monthly_message_count = models.IntegerField(
        default=0
    )

    message_count_period_start = models.DateField(
        default=current_month_start
    )

    api_key = models.CharField(
        max_length=64,
        unique=True,
        blank=True,
    )

    @property
    def effective_plan(self):
        """A known access end is enforced even when the final webhook is late."""
        if (
            self.stripe_subscription_id
            and self.stripe_subscription_status
            and self.stripe_subscription_status
            not in {"active", "trialing"}
        ):
            return self.PLAN_FREE

        if (
            self.subscription_ends_at
            and self.subscription_ends_at <= timezone.now()
        ):
            return self.PLAN_FREE

        return self.plan

    @property
    def has_paid_plan(self):
        """Return True for Premium or Pro users."""
        return self.effective_plan in {
            self.PLAN_PREMIUM,
            self.PLAN_PRO,
        }

    @property
    def is_premium(self):
        return self.effective_plan == self.PLAN_PREMIUM

    @property
    def is_pro(self):
        return self.effective_plan == self.PLAN_PRO

    def reset_monthly_count(self):
        """
        Reset the message counter when a new calendar month begins.

        The reset is based on the calendar month and is independent
        of subscription or plan changes.
        """
        month_start = current_month_start()

        type(self).objects.filter(
            pk=self.pk
        ).exclude(
            message_count_period_start=month_start
        ).update(
            monthly_message_count=0,
            message_count_period_start=month_start,
        )

        self.refresh_from_db(
            fields=[
                "monthly_message_count",
                "message_count_period_start",
            ]
        )

    def reserve_message_slot(self, monthly_limit):
        """
        Atomically reserve one account-wide monthly AI message slot.

        Returns the reservation month when successful.
        Returns None when the monthly message limit is already reached.
        """
        month_start = current_month_start()

        # Reset the counter if this is the first request in a new month.
        type(self).objects.filter(
            pk=self.pk
        ).exclude(
            message_count_period_start=month_start
        ).update(
            monthly_message_count=0,
            message_count_period_start=month_start,
        )

        queryset = type(self).objects.filter(
            pk=self.pk,
            message_count_period_start=month_start,
        )

        if monthly_limit is not None:
            queryset = queryset.filter(
                monthly_message_count__lt=monthly_limit
            )

        updated = queryset.update(
            monthly_message_count=(
                models.F("monthly_message_count") + 1
            )
        )

        self.refresh_from_db(
            fields=[
                "monthly_message_count",
                "message_count_period_start",
            ]
        )

        if updated:
            return month_start

        return None

    def release_message_slot(self, period_start):
        """
        Release a previously reserved AI message slot.

        The reservation is released only when the stored counter
        still belongs to the same calendar month.
        """
        if period_start is None:
            return

        type(self).objects.filter(
            pk=self.pk,
            message_count_period_start=period_start,
            monthly_message_count__gt=0,
        ).update(
            monthly_message_count=(
                models.F("monthly_message_count") - 1
            )
        )

        self.refresh_from_db(
            fields=[
                "monthly_message_count",
                "message_count_period_start",
            ]
        )

    def generate_api_key(self):
        """Generate and save a new API key for the user."""
        self.api_key = secrets.token_hex(32)

        self.save(
            update_fields=["api_key"]
        )

    def __str__(self):
        return f"{self.user.username} Profile"