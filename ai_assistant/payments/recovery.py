"""Fail-closed eligibility for owner-initiated legacy Test Mode recovery."""
from django.utils import timezone

from .webhooks import get_plan_from_subscription


def recovery_reason(subscription):
    """Return an actionable explanation and whether an in-place change is safe."""
    if get_plan_from_subscription(subscription) != "free":
        return "", False
    reason = "Your existing subscription uses a price that is not a current Premium or Pro price."
    if subscription.get("livemode") is not False:
        return reason + " Contact support to review this live subscription.", False
    items = subscription.get("items") or {}
    data = items.get("data") or []
    if items.get("has_more") or len(data) != 1:
        return reason + " Contact support to review its subscription items.", False
    item = data[0]
    price = item.get("price") or {}
    recurring = price.get("recurring") or {}
    end = subscription.get("cancel_at") or (
        subscription.get("current_period_end") or item.get("current_period_end")
        if subscription.get("cancel_at_period_end") else None)
    invoice = subscription.get("latest_invoice")
    if (subscription.get("status") != "active"
            or subscription.get("collection_method") != "charge_automatically"
            or any(subscription.get(key) for key in
                   ("pending_update", "schedule", "pause_collection", "pending_setup_intent"))
            or not isinstance(invoice, dict) or invoice.get("status") != "paid"
            or (end and end <= timezone.now().timestamp())):
        return reason + " Open Manage subscription to resolve payment or cancellation, or contact support.", False
    if (not item.get("id") or not price.get("id") or item.get("quantity", 1) != 1
            or recurring.get("interval") != "month" or recurring.get("interval_count", 1) != 1
            or recurring.get("usage_type", "licensed") != "licensed"
            or price.get("billing_scheme", "per_unit") != "per_unit"
            or price.get("transform_quantity") or type(price.get("unit_amount")) is not int):
        return reason + " Contact support to review this unsupported price structure.", False
    if price.get("currency") == "sek":
        if any(subscription.get(key) for key in (
                "discount", "discounts", "default_tax_rates", "transfer_data", "on_behalf_of",
                "application_fee_percent", "pending_invoice_item_interval", "billing_thresholds")) or (
                subscription.get("automatic_tax") or {}).get("enabled") or item.get("tax_rates"):
            return reason + " Contact support to preserve custom tax or billing settings during currency migration.", False
        return reason + " Replace this legacy SEK Test Mode subscription with a current USD plan below.", True
    if price.get("currency") != "usd":
        return reason + " Changing its currency requires ending the old subscription before creating a USD replacement. Contact support for a controlled migration; do not start another checkout while it is open.", False
    return reason + " Choose a current USD plan below to update this same Test Mode subscription.", True


def recovery_source(subscription):
    item = subscription["items"]["data"][0]
    return {"subscription": subscription["id"], "item": item["id"],
            "price": item["price"]["id"]}


def replacement_parameters(subscription, profile, target):
    """Freeze the agreed terms; retrying never changes the provider request."""
    end = subscription.get("cancel_at")
    if not end and subscription.get("cancel_at_period_end"):
        end = subscription.get("current_period_end") or subscription["items"]["data"][0].get("current_period_end")
        if not end:
            raise ValueError("Missing cancellation end")
    result = {"customer": profile.stripe_customer_id,
              "collection_method": "charge_automatically", "payment_behavior": "error_if_incomplete",
              "proration_behavior": "none",
              "metadata": {"plan": target, "user_id": str(profile.user_id)}}
    if end:
        result["cancel_at"] = end
    for field in ("default_payment_method", "default_source"):
        value = subscription.get(field)
        if value:
            result[field] = value.get("id") if isinstance(value, dict) else value
    return result


def run_replacement(profile, attempt):
    """Caller holds the profile lock. Never create until the old contract is ended."""
    import stripe
    from datetime import timedelta
    from django.conf import settings
    from .pricing import PLAN_CONFIG
    from .state import validate_subscription, TERMINAL
    from .webhooks import update_profile_from_subscription

    inventory = list(stripe.Subscription.list(customer=profile.stripe_customer_id,
        status="all", limit=100, api_key=settings.STRIPE_SECRET_KEY).auto_paging_iter())
    for sub in inventory:
        validate_subscription(profile, sub)
    replacements = [sub for sub in inventory if
        (sub.get("metadata") or {}).get("recovery") == str(attempt.key)]
    others = [sub for sub in inventory if sub.get("status") not in TERMINAL
        and sub.get("id") != attempt.source_subscription and sub not in replacements]
    if others or len(replacements) > 1:
        raise ValueError("Conflicting subscription inventory")
    if replacements:
        current = replacements[0]
        if any(sub.get("id") == attempt.source_subscription and sub.get("status") not in TERMINAL
               for sub in inventory):
            raise ValueError("Source contract remains open")
    else:
        if timezone.now() - attempt.started_at > timedelta(hours=23):
            raise ValueError("Recovery needs support after provider retry window")
        sessions = stripe.checkout.Session.list(customer=profile.stripe_customer_id,
            limit=100, api_key=settings.STRIPE_SECRET_KEY)
        if any(s.get("mode") == "subscription" and s.get("status") == "open"
               for s in sessions.auto_paging_iter()):
            raise ValueError("Existing checkout requires resolution")
        for status in ("open", "draft"):
            invoices = stripe.Invoice.list(customer=profile.stripe_customer_id, status=status,
                limit=100, api_key=settings.STRIPE_SECRET_KEY)
            if any(invoices.auto_paging_iter()):
                raise ValueError("Outstanding invoices require management")
        pending_items = stripe.InvoiceItem.list(customer=profile.stripe_customer_id,
            pending=True, limit=100, api_key=settings.STRIPE_SECRET_KEY)
        if any(pending_items.auto_paging_iter()):
            raise ValueError("Pending invoice items require management")
        source = stripe.Subscription.retrieve(attempt.source_subscription,
            expand=["latest_invoice"], api_key=settings.STRIPE_SECRET_KEY)
        validate_subscription(profile, source)
        if source.get("id") != attempt.source_subscription:
            raise ValueError("Source identifier mismatch")
        if source.get("status") not in TERMINAL:
            if recovery_source(source) != attempt.source:
                raise ValueError("Source item or price changed")
            if not recovery_reason(source)[1] or source["items"]["data"][0]["price"]["currency"] != "sek":
                raise ValueError("Source is no longer eligible")
            if replacement_parameters(source, profile, attempt.plan) != attempt.parameters:
                raise ValueError("Source terms changed")
            stripe.Subscription.cancel(source["id"], invoice_now=False, prorate=False,
                api_key=settings.STRIPE_SECRET_KEY)
            source = stripe.Subscription.retrieve(source["id"], api_key=settings.STRIPE_SECRET_KEY)
            validate_subscription(profile, source)
            if source.get("id") != attempt.source_subscription or source.get("status") not in TERMINAL:
                raise ValueError("Source cancellation is not confirmed")
        update_profile_from_subscription(profile, source)
        # Recheck the complete inventory after cancellation, before creation.
        inventory = list(stripe.Subscription.list(customer=profile.stripe_customer_id,
            status="all", limit=100, api_key=settings.STRIPE_SECRET_KEY).auto_paging_iter())
        for sub in inventory:
            validate_subscription(profile, sub)
        if any(sub.get("status") not in TERMINAL for sub in inventory):
            raise ValueError("A subscription is still open")
        product = stripe.Product.create(api_key=settings.STRIPE_SECRET_KEY,
            name=PLAN_CONFIG[attempt.plan]["name"],
            idempotency_key="ai-assistant-recovery-product-v1-" + attempt.plan)
        params = dict(attempt.parameters)
        params["metadata"] = dict(params["metadata"], recovery=str(attempt.key))
        current = stripe.Subscription.create(**params,
            items=[{"quantity": 1, "price_data": {"currency": "usd",
                "unit_amount": PLAN_CONFIG[attempt.plan]["unit_amount"],
                "recurring": {"interval": "month"}, "product": product.id}}],
            api_key=settings.STRIPE_SECRET_KEY, idempotency_key="replace-" + str(attempt.key))
        validate_subscription(profile, current)
    if (not current.get("id") or current.get("id") == attempt.source_subscription
            or (current.get("metadata") or {}).get("recovery") != str(attempt.key)
            or get_plan_from_subscription(current) != attempt.plan):
        raise ValueError("Replacement identity mismatch")
    update_profile_from_subscription(profile, current)
    if not profile.has_paid_plan:
        raise ValueError("Replacement requires payment or management")
    attempt.replacement_subscription = current["id"]
    attempt.completed = True
    attempt.save(update_fields=["replacement_subscription", "completed"])
