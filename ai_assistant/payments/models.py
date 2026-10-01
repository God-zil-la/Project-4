from django.db import models
from django.utils import timezone
import uuid


class SubscriptionChange(models.Model):
    """Durable owner consent and provider retry identity, separate from access."""
    profile = models.OneToOneField("accounts.UserProfile", on_delete=models.CASCADE)
    key = models.UUIDField(default=uuid.uuid4, editable=False)
    action = models.CharField(max_length=20)
    source = models.JSONField(default=dict)
    parameters = models.JSONField(default=dict)
    schedule_id = models.CharField(max_length=255, blank=True)
    target_price = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, default="confirming")
    started_at = models.DateTimeField(default=timezone.now)


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


class StoreIdentity(models.Model):
    """Random account binding; retained as a tombstone after account erasure."""
    profile = models.OneToOneField('accounts.UserProfile', null=True,
                                  on_delete=models.SET_NULL, related_name='store_identity')
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)


class StoreSubscription(models.Model):
    """Provider-owned state. Stripe must never write these records."""
    identity = models.ForeignKey(StoreIdentity, on_delete=models.PROTECT)
    provider = models.CharField(max_length=10, choices=[('apple', 'Apple'), ('google', 'Google')])
    environment = models.CharField(max_length=12)
    # Apple originalTransactionId or SHA256 of Google purchaseToken.
    reference = models.CharField(max_length=128)
    encrypted_token = models.TextField(blank=True)
    product_id = models.CharField(max_length=255)
    base_plan_id = models.CharField(max_length=63, blank=True)
    plan = models.CharField(max_length=20)
    state = models.CharField(max_length=32)
    expires_at = models.DateTimeField(null=True)
    auto_renew = models.BooleanField(default=False)
    verified_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['provider', 'environment', 'reference'],
                                              name='unique_store_subscription')]


class StoreEvent(models.Model):
    """Only successful event IDs, never signed payloads or purchase tokens."""
    provider = models.CharField(max_length=10)
    environment = models.CharField(max_length=12)
    event_id = models.CharField(max_length=255)
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['provider', 'environment', 'event_id'],
                                              name='unique_store_event')]


class StorePurchaseIntent(models.Model):
    """Cross-provider checkout mutex; uncertain purchases require reconciliation."""
    profile = models.OneToOneField('accounts.UserProfile', on_delete=models.CASCADE)
    provider = models.CharField(max_length=10)
    product_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
