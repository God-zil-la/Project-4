"""Signature-verified, retryable subscription reconciliation."""
import logging
import json
from datetime import datetime, timezone as dt_timezone
import stripe
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from ai_assistant.accounts.models import UserProfile
from .models import StripeEvent, SubscriptionRecovery
from .emails import invoice_subscription, queue_subscription_emails
from .pricing import CURRENCY, PLAN_CONFIG

logger = logging.getLogger(__name__)
ACTIVE_SUBSCRIPTION_STATUSES = {"active", "trialing"}


def timestamp_to_datetime(timestamp):
    return datetime.fromtimestamp(timestamp, tz=dt_timezone.utc) if timestamp else None


def get_plan_from_subscription(subscription):
    # Derive access from the actual monthly price, so stale metadata cannot keep Pro.
    items = subscription.get("items", {}).get("data", [])
    if len(items) != 1 or items[0].get("quantity", 1) != 1:
        return UserProfile.PLAN_FREE
    price = items[0].get("price", {})
    recurring = price.get("recurring", {})
    if (price.get("currency") != CURRENCY or recurring.get("interval") != "month"
            or recurring.get("interval_count", 1) != 1
            or recurring.get("usage_type", "licensed") != "licensed"
            or price.get("billing_scheme", "per_unit") != "per_unit"
            or price.get("transform_quantity")):
        return UserProfile.PLAN_FREE
    return {config["unit_amount"]: plan for plan, config in PLAN_CONFIG.items()}.get(
        price.get("unit_amount"), UserProfile.PLAN_FREE)


def update_profile_from_subscription(profile, subscription):
    status = subscription.get("status")
    plan = get_plan_from_subscription(subscription)
    active = status in ACTIVE_SUBSCRIPTION_STATUSES and plan != UserProfile.PLAN_FREE
    items = subscription.get("items", {}).get("data", [])
    period_end = subscription.get("current_period_end")
    if not period_end and items:
        period_end = items[0].get("current_period_end")
    profile.stripe_customer_id = subscription.get("customer")
    profile.stripe_subscription_id = subscription.get("id")
    profile.stripe_subscription_status = status
    profile.subscription_current_period_end = timestamp_to_datetime(period_end)
    profile.subscription_cancel_at_period_end = bool(subscription.get("cancel_at_period_end")) and status not in {"canceled", "incomplete_expired"}
    # canceled_at is the request time for scheduled cancellations, not access expiry.
    end = (subscription.get("ended_at") if status in {"canceled", "incomplete_expired"} else
           subscription.get("cancel_at") or (period_end if profile.subscription_cancel_at_period_end else None))
    profile.subscription_ends_at = timestamp_to_datetime(end)
    active = active and not (profile.subscription_ends_at and profile.subscription_ends_at <= timezone.now())
    profile.is_subscribed = active
    profile.plan = plan if active else UserProfile.PLAN_FREE
    profile.save(update_fields=["stripe_customer_id", "stripe_subscription_id",
        "stripe_subscription_status", "subscription_current_period_end", "is_subscribed", "plan",
        "subscription_cancel_at_period_end", "subscription_ends_at"])


@csrf_exempt
@require_POST
def stripe_webhook(request):
    if not settings.STRIPE_WEBHOOK_SECRET or not settings.STRIPE_SECRET_KEY:
        return HttpResponse(status=503)
    try:
        stripe.Webhook.construct_event(
            request.body, request.headers.get("Stripe-Signature", ""),
            settings.STRIPE_WEBHOOK_SECRET)
        event = json.loads(request.body)
    except (ValueError, TypeError, AttributeError, KeyError, stripe.error.SignatureVerificationError):
        return HttpResponse(status=400)
    if not isinstance(event, dict) or type(event.get("livemode")) is not bool:
        return HttpResponse(status=400)
    if event["livemode"] != settings.STRIPE_SECRET_KEY.startswith(("sk_live_", "rk_live_")):
        return HttpResponse(status=400)
    event_type = event.get("type")
    if not isinstance(event_type, str):
        return HttpResponse(status=400)
    if event_type not in {"checkout.session.completed", "customer.subscription.created",
                          "customer.subscription.updated", "customer.subscription.deleted",
                          "invoice.paid", "invoice.payment_succeeded"}:
        return HttpResponse(status=200)
    data = event.get("data")
    obj = data.get("object") if isinstance(data, dict) else None
    if not isinstance(obj, dict):
        return HttpResponse(status=400)
    invoice_event = event_type in {"invoice.paid", "invoice.payment_succeeded"}
    checkout = event_type == "checkout.session.completed"
    if checkout and obj.get("mode") != "subscription":
        return HttpResponse(status=200)
    subscription_id = invoice_subscription(obj) if invoice_event else (obj.get("subscription") if checkout else obj.get("id"))
    if invoice_event and not subscription_id:
        return HttpResponse(status=200)
    identifiers = (event.get("id"), subscription_id, obj.get("customer"))
    if any(not isinstance(value, str) or not value or len(value) > 255 for value in identifiers):
        return HttpResponse(status=400)
    metadata = obj.get("metadata") or {}
    if not isinstance(metadata, dict):
        return HttpResponse(status=400)
    user_id = obj.get("client_reference_id") if checkout else metadata.get("user_id")
    if checkout and user_id is None:
        return HttpResponse(status=400)
    if user_id is not None and (not isinstance(user_id, str) or not user_id.isascii()
            or not user_id.isdecimal() or len(user_id) > 19 or not 0 < int(user_id) < 2**63):
        return HttpResponse(status=400)
    try:
        with transaction.atomic():
            # A unique event row serializes duplicate deliveries and rolls back on failure.
            _, created = StripeEvent.objects.get_or_create(event_id=event["id"])
            if not created:
                return HttpResponse(status=200)
            profiles = UserProfile.objects.select_for_update()
            if checkout:
                profile = profiles.filter(user_id=obj.get("client_reference_id")).first()
            else:
                profile = profiles.filter(stripe_subscription_id=subscription_id).first()
                if profile is None:
                    profile = profiles.filter(stripe_customer_id=obj["customer"]).first()
                if profile is None:
                    profile = profiles.filter(user_id=(obj.get("metadata") or {}).get("user_id")).first()
            if profile is None:
                return HttpResponse(status=200)
            if profile.stripe_customer_id and profile.stripe_customer_id != obj["customer"]:
                return HttpResponse(status=200)
            recovery = SubscriptionRecovery.objects.filter(profile=profile, completed=False).first()
            # Old subscriptions must never revoke or overwrite the current subscription.
            if (profile.stripe_subscription_id and profile.stripe_subscription_id != subscription_id
                    and not checkout):
                if not recovery or profile.stripe_subscription_id != recovery.source_subscription:
                    return HttpResponse(status=200)
            if (checkout and profile.stripe_subscription_id
                    and profile.stripe_subscription_id != subscription_id
                    and profile.stripe_subscription_status not in {"canceled", "incomplete_expired"}):
                return HttpResponse(status=200)
            # Fetch inside the profile lock: delivery order does not determine access.
            subscription = stripe.Subscription.retrieve(
                subscription_id, api_key=settings.STRIPE_SECRET_KEY)
            if subscription.get("id") != subscription_id:
                raise ValueError("Subscription identifier mismatch")
            if subscription.get("customer") != obj["customer"]:
                raise ValueError("Subscription customer mismatch")
            metadata_user = (subscription.get("metadata") or {}).get("user_id")
            if metadata_user and str(metadata_user) != str(profile.user_id):
                raise ValueError("Subscription owner mismatch")
            if recovery and subscription_id != recovery.source_subscription:
                # A creation/payment webhook may arrive before the migration HTTP
                # response. Adopt only the saved replacement after confirmed end.
                if ((subscription.get("metadata") or {}).get("recovery") != str(recovery.key)
                        or subscription.get("livemode") is not False
                        or get_plan_from_subscription(subscription) != recovery.plan):
                    raise ValueError("Recovery replacement mismatch")
                source = stripe.Subscription.retrieve(recovery.source_subscription,
                    api_key=settings.STRIPE_SECRET_KEY)
                if (source.get("id") != recovery.source_subscription
                        or source.get("customer") != profile.stripe_customer_id
                        or source.get("status") not in {"canceled", "incomplete_expired"}):
                    raise ValueError("Recovery source is still open")
            update_profile_from_subscription(profile, subscription)
            queue_subscription_emails(profile, subscription, obj.get("id") if invoice_event else None)
    except Exception:
        logger.error("Stripe subscription reconciliation failed; retry required.")
        return HttpResponse(status=500)
    return HttpResponse(status=200)
