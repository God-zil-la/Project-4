"""Reconcile entitlement separately from the existence of a billing contract."""
import stripe
from django.conf import settings
from ai_assistant.accounts.models import UserProfile
from .webhooks import update_profile_from_subscription

TERMINAL = {"canceled", "incomplete_expired"}


def has_existing_subscription(profile):
    return bool(profile.stripe_subscription_id) and profile.stripe_subscription_status not in TERMINAL


def validate_subscription(profile, subscription):
    owner = (subscription.get("metadata") or {}).get("user_id")
    if (subscription.get("customer") != profile.stripe_customer_id
            or (owner and str(owner) != str(profile.user_id))
            or subscription.get("livemode") is not settings.STRIPE_SECRET_KEY.startswith(("sk_live_", "rk_live_"))):
        raise ValueError("Subscription ownership or mode mismatch")


def clear_subscription(profile):
    from .models import SubscriptionChange
    # A confirmed empty inventory must not leave a promised future downgrade.
    SubscriptionChange.objects.filter(profile=profile, status="scheduled").update(status="removed")
    profile.stripe_subscription_id = None
    profile.stripe_subscription_status = None
    profile.subscription_cancel_at_period_end = False
    profile.subscription_ends_at = None
    profile.subscription_current_period_end = None
    profile.plan = UserProfile.PLAN_FREE
    profile.is_subscribed = False
    profile.save(update_fields=["stripe_subscription_id", "stripe_subscription_status",
        "subscription_cancel_at_period_end", "subscription_ends_at",
        "subscription_current_period_end", "plan", "is_subscribed"])


def reconcile_customer(profile):
    """Caller holds the profile lock. Verify the full customer inventory first.

    A missing/stale subscription link is cleared only after a successful complete
    listing. Provider failures and conflicting ownership always fail closed.
    """
    if not profile.stripe_customer_id:
        if profile.stripe_subscription_id:
            raise ValueError("Missing billing customer")
        clear_subscription(profile)
        return
    subscriptions = list(stripe.Subscription.list(customer=profile.stripe_customer_id,
        status="all", limit=100, api_key=settings.STRIPE_SECRET_KEY).auto_paging_iter())
    for subscription in subscriptions:
        validate_subscription(profile, subscription)
    current = [s for s in subscriptions if s.get("status") not in TERMINAL]
    if len(current) > 1:
        raise ValueError("Multiple nonterminal subscriptions require support")
    selected = current[0] if current else next(
        (s for s in subscriptions if s.get("id") == profile.stripe_subscription_id), None)
    if selected:
        update_profile_from_subscription(profile, selected)
    else:
        clear_subscription(profile)
    return selected
