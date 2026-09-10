"""Serialized subscription continuation with durable, bounded provider retries."""
from datetime import timedelta

import stripe
from django.conf import settings
from django.utils import timezone

from .models import CheckoutAttempt, SubscriptionChange, SubscriptionRecovery
from .pricing import PLAN_CONFIG
from .state import TERMINAL, validate_subscription
from .webhooks import get_plan_from_subscription


class ChangeBlocked(ValueError):
    """An internal guard rejection with a safe, fixed diagnostic reason."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def identifier(value):
    return value.get("id") if isinstance(value, dict) else value


def snapshot(subscription):
    item = subscription["items"]["data"][0]
    return {"subscription": subscription["id"], "item": item["id"],
            "price": item["price"]["id"], "plan": get_plan_from_subscription(subscription),
            "end": subscription.get("current_period_end") or item.get("current_period_end"),
            "start": subscription.get("current_period_start") or item.get("current_period_start")}


def is_current_pending_proration(item, subscription):
    """Allow only provider-generated prorations with complete current ownership."""
    if (not isinstance(item, dict) or item.get("object") != "invoiceitem"
            or not item.get("id") or item.get("proration") is not True
            or "invoice" not in item or item["invoice"] is not None
            or identifier(item.get("customer")) != identifier(subscription.get("customer"))
            or type(item.get("livemode")) is not bool
            or item["livemode"] is not subscription.get("livemode")):
        return False
    parent = item.get("parent")
    if not isinstance(parent, dict) or parent.get("type") != "subscription_details":
        return False
    details = parent.get("subscription_details")
    if not isinstance(details, dict):
        return False
    subscription_id = identifier(details.get("subscription"))
    item_id = identifier(details.get("subscription_item"))
    current_items = subscription.get("items") or {}
    if (not subscription_id or subscription_id != subscription.get("id")
            or not isinstance(item_id, str) or not item_id
            or current_items.get("has_more")
            or not any(current.get("id") == item_id
                       for current in current_items.get("data", []))):
        return False
    # Do not let conflicting legacy identity fields override the provider parent.
    return all(key not in item or identifier(item[key]) == expected
               for key, expected in (("subscription", subscription_id),
                                     ("subscription_item", item_id)))


def inventory(profile, subscription):
    entries = list(stripe.Subscription.list(customer=profile.stripe_customer_id,
        status="all", limit=100, api_key=settings.STRIPE_SECRET_KEY).auto_paging_iter())
    for entry in entries:
        validate_subscription(profile, entry)
    current = [entry for entry in entries if entry.get("status") not in TERMINAL]
    if len(current) != 1 or current[0].get("id") != subscription["id"]:
        raise ChangeBlocked("conflicting_subscription_inventory")
    if SubscriptionRecovery.objects.filter(profile=profile, completed=False).exists():
        raise ChangeBlocked("pending_legacy_migration")
    if CheckoutAttempt.objects.filter(profile=profile).exists():
        # Completed checkout rows are retained by the checkout implementation.
        attempt = CheckoutAttempt.objects.get(profile=profile)
        if not attempt.session_id:
            raise ChangeBlocked("unconfirmed_checkout")
        session = stripe.checkout.Session.retrieve(attempt.session_id, api_key=settings.STRIPE_SECRET_KEY)
        if session.get("status") != "complete" or identifier(session.get("subscription")) != subscription["id"]:
            raise ChangeBlocked("conflicting_checkout_intent")
    sessions = stripe.checkout.Session.list(customer=profile.stripe_customer_id,
        limit=100, api_key=settings.STRIPE_SECRET_KEY)
    if any(s.get("mode") == "subscription" and s.get("status") == "open"
           for s in sessions.auto_paging_iter()):
        raise ChangeBlocked("open_checkout")
    for status in ("open", "draft", "uncollectible"):
        invoices = stripe.Invoice.list(customer=profile.stripe_customer_id, status=status,
            limit=100, api_key=settings.STRIPE_SECRET_KEY)
        if any(invoices.auto_paging_iter()):
            raise ChangeBlocked("outstanding_" + status + "_invoice")
    items = stripe.InvoiceItem.list(customer=profile.stripe_customer_id, pending=True,
        limit=100, api_key=settings.STRIPE_SECRET_KEY)
    if any(not is_current_pending_proration(item, subscription)
           for item in items.auto_paging_iter()):
        raise ChangeBlocked("pending_invoice_items")


def eligible(subscription, allowed_schedule=""):
    """Restrict changes to a fully paid, simple current monthly contract."""
    items = subscription.get("items") or {}
    data = items.get("data") or []
    invoice = subscription.get("latest_invoice")
    if (get_plan_from_subscription(subscription) not in PLAN_CONFIG or items.get("has_more")
            or len(data) != 1 or subscription.get("status") != "active"
            or subscription.get("collection_method") != "charge_automatically"
            or not isinstance(invoice, dict) or invoice.get("status") != "paid"
            or identifier(subscription.get("schedule")) not in (None, "", allowed_schedule)
            or any(subscription.get(key) for key in (
                "pending_update", "pause_collection", "pending_setup_intent", "trial_end",
                "discount", "discounts", "default_tax_rates", "transfer_data", "on_behalf_of",
                "application_fee_percent", "pending_invoice_item_interval", "billing_thresholds"))
            or (subscription.get("automatic_tax") or {}).get("enabled")):
        raise ChangeBlocked("unsupported_billing_state")
    item = data[0]
    if (not item.get("id") or not (item.get("price") or {}).get("id")
            or any(item.get(k) for k in ("tax_rates", "discounts", "billing_thresholds"))):
        raise ChangeBlocked("unsupported_item_settings")
    source = snapshot(subscription)
    if type(source["end"]) is not int or source["end"] <= timezone.now().timestamp():
        raise ChangeBlocked("invalid_renewal_boundary")
    if subscription.get("cancel_at") and (not subscription.get("cancel_at_period_end")
            or subscription["cancel_at"] != source["end"]):
        raise ChangeBlocked("custom_cancellation")
    return source


def schedule_state(change, subscription, schedule=None):
    """Read the provider schedule; intent alone never promises a downgrade."""
    if schedule is None:
        schedule = stripe.SubscriptionSchedule.retrieve(change.schedule_id,
            expand=["phases.items.price"], api_key=settings.STRIPE_SECRET_KEY)
    if (schedule.get("id") != change.schedule_id
            or identifier(schedule.get("customer")) != subscription.get("customer")
            or schedule.get("livemode") is not subscription.get("livemode")):
        raise ValueError("Schedule owner or mode mismatch")
    if subscription.get("status") in TERMINAL:
        return "removed"
    if schedule.get("status") in {"released", "completed", "canceled"}:
        return "complete" if get_plan_from_subscription(subscription) == "premium" else "removed"
    if (identifier(schedule.get("subscription")) != subscription["id"]
            or identifier(subscription.get("schedule")) != change.schedule_id):
        return "conflict"
    if subscription.get("cancel_at_period_end") or subscription.get("cancel_at"):
        return "conflict"
    phases = schedule.get("phases") or []
    future = [p for p in phases if p.get("start_date", 0) >= change.source["end"]]
    if (schedule.get("status") != "active" or schedule.get("end_behavior") != "release"
            or (schedule.get("metadata") or {}).get("change") != str(change.key)
            or len(future) != 1):
        return "conflict"
    phase = future[0]
    items = phase.get("items") or []
    if (phase.get("start_date") != change.source["end"] or len(items) != 1
            or items[0].get("quantity") != 1
            or identifier(items[0].get("price")) != change.target_price
            or phase.get("proration_behavior") != "none"
            or any(phase.get(k) for k in ("discounts", "default_tax_rates", "add_invoice_items",
                "trial_end", "transfer_data", "on_behalf_of", "application_fee_percent"))
            or (phase.get("automatic_tax") or {}).get("enabled")):
        return "conflict"
    if get_plan_from_subscription(subscription) == "premium":
        return "complete"
    if subscription.get("status") != "active":
        return "conflict"
    if snapshot(subscription) != change.source:
        return "conflict"
    return "scheduled"


def verified_keep_schedule(change, subscription):
    """Require the exact app-owned two-phase contract before releasing it."""
    if (not change.parameters.get("schedule_configured") or not change.schedule_id
            or change.source.get("plan") != "pro"
            or eligible(subscription, change.schedule_id) != change.source
            or subscription.get("cancel_at_period_end") or subscription.get("cancel_at")):
        raise ChangeBlocked("unsafe_keep_schedule")
    schedule = stripe.SubscriptionSchedule.retrieve(change.schedule_id,
        expand=["phases.items.price"], api_key=settings.STRIPE_SECRET_KEY)
    if (schedule.get("id") != change.schedule_id
            or identifier(schedule.get("customer")) != identifier(subscription.get("customer"))
            or schedule.get("livemode") is not subscription.get("livemode")
            or (schedule.get("metadata") or {}).get("change") != str(change.key)):
        raise ChangeBlocked("unsafe_keep_schedule_owner")
    if (schedule.get("status") == "released" and change.action == "keep"
            and identifier(schedule.get("released_subscription")) == subscription["id"]
            and not schedule.get("subscription") and not subscription.get("schedule")):
        return "complete"
    if (schedule_state(change, subscription, schedule) != "scheduled"
            or identifier(schedule.get("subscription")) != subscription["id"]):
        raise ChangeBlocked("unsafe_keep_schedule_state")
    phases = schedule.get("phases") or []
    expected = change.parameters.get("phases") or []
    if len(phases) != 2 or len(expected) != 2:
        raise ChangeBlocked("unsafe_keep_schedule_phases")
    for index, phase in enumerate(phases):
        items = phase.get("items") or []
        if (phase.get("start_date") != expected[index].get("start_date")
                or len(items) != 1 or items[0].get("quantity") != 1
                or identifier(items[0].get("price")) != (
                    change.source["price"] if index == 0 else change.target_price)
                or phase.get("proration_behavior") != "none"
                or any(phase.get(k) for k in ("discounts", "default_tax_rates",
                    "add_invoice_items", "trial_end", "transfer_data", "on_behalf_of",
                    "application_fee_percent", "billing_thresholds"))
                or any(items[0].get(k) for k in ("discounts", "tax_rates", "billing_thresholds"))
                or (phase.get("automatic_tax") or {}).get("enabled")):
            raise ChangeBlocked("unsafe_keep_schedule_terms")
    if phases[0].get("end_date") != change.source["end"]:
        raise ChangeBlocked("unsafe_keep_schedule_boundary")
    return "scheduled"


def reconcile_change(profile, subscription):
    change = SubscriptionChange.objects.filter(profile=profile).first()
    if not change or change.source.get("subscription") != subscription.get("id"):
        return
    if change.action == "keep":
        if change.status == "complete":
            return
        # A lost release reply is confirmed only from the same released schedule
        # and unchanged authoritative Pro contract. Never infer it from intent.
        try:
            state = verified_keep_schedule(change, subscription)
        except ValueError:
            state = "conflict"
        if state == "complete":
            change.status = "complete"
        elif state == "conflict":
            change.status = "conflict"
    elif change.action == "downgrade" and change.schedule_id:
        # Creation and configuration are separate calls. An unfinished creation
        # remains retryable and must not be mistaken for a confirmed downgrade.
        if not change.parameters.get("schedule_configured"):
            return
        change.status = schedule_state(change, subscription)
    elif change.status == "confirming":
        plan = get_plan_from_subscription(subscription)
        if (not subscription.get("cancel_at_period_end") and not subscription.get("cancel_at")
                and subscription.get("status") == "active"
                and plan == ("pro" if change.action == "upgrade" else change.source["plan"])
                and change.action != "downgrade"
                and not subscription.get("schedule") and not subscription.get("pending_update")
                and snapshot(subscription)["end"] == change.source["end"]):
            change.status = "complete"
    change.save(update_fields=["status"])


def run_change(profile, change, subscription):
    """Caller commits intent first and holds the profile lock during execution."""
    if change.action == "keep":
        state = verified_keep_schedule(change, subscription)
        inventory(profile, subscription)
        if state == "complete":
            return
        if change.status != "confirming" or timezone.now() - change.started_at > timedelta(hours=23):
            raise ChangeBlocked("keep_retry_unavailable")
        # Release leaves the subscription running. Never cancel the schedule,
        # which would cancel its subscription. Preserve any provider cancellation.
        stripe.SubscriptionSchedule.release(change.schedule_id, preserve_cancel_date=True,
            idempotency_key="subscription-change-" + str(change.key) + "-keep",
            api_key=settings.STRIPE_SECRET_KEY)
        return
    if change.status == "complete":
        if (subscription.get("cancel_at_period_end") or subscription.get("cancel_at")
                or subscription.get("status") != "active"):
            raise ValueError("Completed operation no longer describes current billing")
        return
    if change.status == "scheduled":
        if schedule_state(change, subscription) != "scheduled":
            raise ValueError("Schedule changed; refresh Billing")
        return
    if change.status != "confirming":
        raise ValueError("Conflicting schedule requires support")
    if timezone.now() - change.started_at > timedelta(hours=23):
        raise ValueError("Provider retry window expired; contact support")
    if (change.action == "downgrade" and not change.schedule_id
            and change.parameters.get("creation_started")):
        if eligible(subscription, identifier(subscription.get("schedule"))) != change.source:
            raise ValueError("Subscription changed during schedule creation")
        inventory(profile, subscription)
        # Recover only the exact idempotent creation, including a lost response.
        recovered = stripe.SubscriptionSchedule.create(from_subscription=subscription["id"],
            idempotency_key="subscription-change-" + str(change.key) + "-create",
            api_key=settings.STRIPE_SECRET_KEY)
        if (identifier(recovered.get("subscription")) != subscription["id"]
                or identifier(recovered.get("customer")) != profile.stripe_customer_id
                or recovered.get("livemode") is not subscription.get("livemode")
                or identifier(subscription.get("schedule")) not in (None, recovered.get("id"))):
            raise ValueError("Recovered schedule identity mismatch")
        change.schedule_id = recovered["id"]
        change.save(update_fields=["schedule_id"])
    source = eligible(subscription, change.schedule_id)
    if source != change.source:
        raise ValueError("Subscription terms changed; refresh Billing")
    inventory(profile, subscription)
    key = "subscription-change-" + str(change.key)
    api = {"api_key": settings.STRIPE_SECRET_KEY}
    if change.action in {"resume", "upgrade"}:
        params = {"cancel_at_period_end": False, "proration_behavior": "none"}
        if change.action == "upgrade":
            product = stripe.Product.create(name=PLAN_CONFIG["pro"]["name"],
                idempotency_key=key + "-product", **api)
            params.update(items=[{"id": source["item"], "quantity": 1, "price_data": {
                "currency": "usd", "unit_amount": PLAN_CONFIG["pro"]["unit_amount"],
                "recurring": {"interval": "month"}, "product": product.id}}],
                proration_behavior="always_invoice", payment_behavior="error_if_incomplete",
                billing_cycle_anchor="unchanged",
                metadata={"plan": "pro", "user_id": str(profile.user_id)})
        try:
            stripe.Subscription.modify(subscription["id"], **params, idempotency_key=key, **api)
        except stripe.error.CardError:
            if change.action == "upgrade":
                # Only a definitive rejection of this payment request allows a
                # new key. Retrieval failures after a write remain uncertain.
                change.status = "failed"
                change.save(update_fields=["status"])
            raise
        return
    # A canceled Pro contract is continued before attaching a schedule. Persist
    # every stage and explain partial success; do not automatically re-cancel.
    if subscription.get("cancel_at_period_end"):
        if change.schedule_id:
            raise ValueError("Cancellation conflicts with the existing schedule")
        stripe.Subscription.modify(subscription["id"], cancel_at_period_end=False,
            proration_behavior="none", idempotency_key=key + "-continue", **api)
        current = stripe.Subscription.retrieve(subscription["id"], expand=["latest_invoice"], **api)
        validate_subscription(profile, current)
        if current.get("id") != subscription["id"] or current.get("cancel_at_period_end") or current.get("cancel_at"):
            raise ValueError("Continuation is not yet confirmed")
        if eligible(current) != source:
            raise ValueError("Subscription terms changed")
    if not change.target_price:
        product = stripe.Product.create(name=PLAN_CONFIG["premium"]["name"],
            idempotency_key=key + "-product", **api)
        price = stripe.Price.create(currency="usd", unit_amount=PLAN_CONFIG["premium"]["unit_amount"],
            recurring={"interval": "month"}, product=product.id,
            idempotency_key=key + "-price", **api)
        change.target_price = price.id
        change.save(update_fields=["target_price"])
    if not change.schedule_id:
        # Retry creation with the same key even if a response was lost. Never
        # adopt an arbitrary schedule found on the subscription.
        change.parameters["creation_started"] = True
        change.save(update_fields=["parameters"])
        schedule = stripe.SubscriptionSchedule.create(from_subscription=subscription["id"],
            idempotency_key=key + "-create", **api)
        if (identifier(schedule.get("subscription")) != subscription["id"]
                or identifier(schedule.get("customer")) != profile.stripe_customer_id
                or schedule.get("livemode") is not subscription.get("livemode")):
            raise ValueError("Created schedule identity mismatch")
        change.schedule_id = schedule["id"]
        change.save(update_fields=["schedule_id"])
    if not change.parameters.get("phases"):
        schedule = stripe.SubscriptionSchedule.retrieve(change.schedule_id, **api)
        phases = schedule.get("phases") or []
        if (schedule.get("id") != change.schedule_id or len(phases) != 1
                or identifier(schedule.get("subscription")) != subscription["id"]
                or identifier(schedule.get("customer")) != profile.stripe_customer_id
                or schedule.get("livemode") is not subscription.get("livemode")
                or phases[0].get("end_date") != source["end"]
                or not phases[0].get("start_date")):
            raise ValueError("Initial schedule boundary mismatch")
        change.parameters = {"phases": [
            {"start_date": phases[0]["start_date"], "end_date": source["end"],
             "items": [{"price": source["price"], "quantity": 1}], "proration_behavior": "none"},
            {"start_date": source["end"], "iterations": 1,
             "items": [{"price": change.target_price, "quantity": 1}],
             "proration_behavior": "none", "metadata": {"plan": "premium"}}]}
        change.save(update_fields=["parameters"])
    stripe.SubscriptionSchedule.modify(change.schedule_id, phases=change.parameters["phases"],
        end_behavior="release", proration_behavior="none", metadata={"change": str(change.key)},
        idempotency_key=key + "-configure", **api)
    change.parameters["schedule_configured"] = True
    change.save(update_fields=["parameters"])
