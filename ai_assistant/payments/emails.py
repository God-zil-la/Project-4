"""Billing notifications: persist inside the webhook transaction, deliver after commit.

SMTP has no idempotency key. Never automatically retry an ambiguous delivery:
failed/sending rows require provider-log review before any manual recovery.
"""
import logging
from decimal import Decimal
import stripe
from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from .models import BillingEmail
from .pricing import PLAN_CONFIG

logger = logging.getLogger(__name__)


def deliver(pk):
    if not BillingEmail.objects.filter(pk=pk, status="pending").update(status="sending"):
        return
    notice = BillingEmail.objects.get(pk=pk)
    try:
        if send_mail(notice.subject, notice.body, settings.DEFAULT_FROM_EMAIL,
                     [notice.recipient], fail_silently=False) != 1:
            raise RuntimeError("Email backend did not accept the message")
    except Exception:
        BillingEmail.objects.filter(pk=pk).update(status="failed")
        logger.error("Billing email delivery failed; notification %s requires review.", pk)
    else:
        BillingEmail.objects.filter(pk=pk).update(status="sent", sent_at=timezone.now())


def queue(key, profile, subject, body):
    if not profile.user.email:
        logger.error("Billing notification has no recipient; profile %s requires review.", profile.pk)
        return
    notice, _ = BillingEmail.objects.get_or_create(key=key, defaults={
        "recipient": profile.user.email, "subject": subject, "body": body})
    transaction.on_commit(lambda: deliver(notice.pk), robust=True)


def invoice_subscription(invoice):
    return invoice.get("subscription") or (invoice.get("parent") or {}).get(
        "subscription_details", {}).get("subscription")


def paid_plan(invoice):
    """Read the billed plan, not a later subscription upgrade/downgrade."""
    from .webhooks import get_plan_from_subscription
    lines = invoice.get("lines") or {}
    if lines.get("has_more"):
        return None
    plans = set()
    for line in lines.get("data", []):
        if line.get("amount", 0) <= 0:
            continue
        price = line.get("price")
        if not price:
            price_id = ((line.get("pricing") or {}).get("price_details") or {}).get("price")
            if price_id:
                price = stripe.Price.retrieve(price_id, api_key=settings.STRIPE_SECRET_KEY)
        if isinstance(price, str):
            price = stripe.Price.retrieve(price, api_key=settings.STRIPE_SECRET_KEY)
        plan = get_plan_from_subscription({"items": {"data": [{
            "quantity": line.get("quantity", 1), "price": price or {}}]}})
        if plan in PLAN_CONFIG:
            plans.add(plan)
    return next(iter(plans)) if len(plans) == 1 else None


def queue_subscription_emails(profile, subscription, invoice_id=None):
    latest = subscription.get("latest_invoice")
    invoice_id = invoice_id or (latest.get("id") if isinstance(latest, dict) else latest)
    if isinstance(invoice_id, str) and invoice_id:
        invoice = stripe.Invoice.retrieve(invoice_id, api_key=settings.STRIPE_SECRET_KEY)
        if (invoice.get("id") != invoice_id or invoice.get("customer") != subscription["customer"]
                or invoice_subscription(invoice) != subscription["id"]
                or invoice.get("livemode") != settings.STRIPE_SECRET_KEY.startswith(("sk_live_", "rk_live_"))):
            raise ValueError("Invoice ownership or mode mismatch")
        if (invoice.get("status") == "paid" and invoice.get("paid") is True
                and invoice.get("currency") == "usd" and type(invoice.get("amount_paid")) is int
                and invoice["amount_paid"] > 0 and invoice.get("amount_remaining") == 0):
            plan = paid_plan(invoice)
            if plan:
                config = PLAN_CONFIG[plan]
                body = (f"Payment confirmed for {config['name']}.\n"
                    f"Plan price: ${Decimal(config['unit_amount']) / 100:.2f} USD/month.\n"
                    f"Amount paid: ${Decimal(invoice['amount_paid']) / 100:.2f} USD.\n"
                    f"Invoice: {invoice_id}\nThank you for using AI Assistant.")
                queue(f"paid:{invoice_id}", profile, "AI Assistant payment confirmation", body)
    if subscription.get("cancel_at_period_end") or subscription.get("status") == "canceled" or subscription.get("cancel_at"):
        # Stripe preserves canceled_at from the cancellation request through final deletion.
        marker = subscription.get("canceled_at") or subscription.get("cancel_at") or "canceled"
        end = profile.subscription_ends_at
        if end:
            date = end.strftime("%B %d, %Y at %H:%M UTC")
            detail = (f"Paid access continues through {date}." if profile.is_subscribed
                      else f"Subscription end date: {date}. Paid access is currently unavailable.")
        else:
            detail = "The access end date is not available. Check your billing page for current access status."
        queue(f"cancel:{subscription['id']}:{marker}", profile,
              "AI Assistant cancellation confirmation", "Your subscription cancellation is confirmed.\n" + detail)
