from django.db import models
from django.utils import timezone
import uuid


class SubscriptionRecovery(models.Model):
    """Committed before ending a legacy contract; retained across uncertain replies."""
    profile = models.OneToOneField("accounts.UserProfile", on_delete=models.CASCADE)
    key = models.UUIDField(default=uuid.uuid4, editable=False)
    source_subscription = models.CharField(max_length=255)
    source = models.JSONField(default=dict)
    plan = models.CharField(max_length=20)
    parameters = models.JSONField(default=dict)
    started_at = models.DateTimeField(default=timezone.now)
    completed = models.BooleanField(default=False)
    replacement_subscription = models.CharField(max_length=255, blank=True)


class CheckoutAttempt(models.Model):
    """Durable checkout intent shared by every browser tab and retry."""
    profile = models.OneToOneField("accounts.UserProfile", on_delete=models.CASCADE)
    key = models.UUIDField(default=uuid.uuid4, editable=False)
    plan = models.CharField(max_length=20)
    session_id = models.CharField(max_length=255, blank=True)
    started_at = models.DateTimeField(default=timezone.now)
    success_url = models.TextField()
    cancel_url = models.TextField()

class StripeEvent(models.Model):
    """Processed event identifiers only; never persist payment payloads."""
    event_id = models.CharField(max_length=255, unique=True)
    processed_at = models.DateTimeField(auto_now_add=True)


class BillingEmail(models.Model):
    """Durable notification intent with an at-most-once delivery claim."""
    key = models.CharField(max_length=320, unique=True)
    recipient = models.EmailField()
    subject = models.CharField(max_length=255)
    body = models.TextField()
    status = models.CharField(max_length=12, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
