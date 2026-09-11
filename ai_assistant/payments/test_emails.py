import hashlib
import hmac
import json
import time
from copy import deepcopy
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.db import transaction
from django.test import TestCase
from django.urls import reverse
from .emails import deliver, queue
from .models import BillingEmail, StripeEvent


class BillingEmailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("payer", "payer@example.org")
        profile = self.user.profile
        profile.stripe_customer_id = "cus_payer"
        profile.stripe_subscription_id = "sub_payer"
        profile.save()
        self.subscription = {"id": "sub_payer", "customer": "cus_payer", "status": "active",
            "latest_invoice": "in_paid", "metadata": {"user_id": str(self.user.pk)},
            "current_period_end": 2000000000, "cancel_at_period_end": False,
            "items": {"data": [{"quantity": 1, "price": {"currency": "usd", "unit_amount": 2900,
                "recurring": {"interval": "month"}}}]}}
        self.invoice = {"id": "in_paid", "customer": "cus_payer", "subscription": "sub_payer",
            "livemode": False, "status": "paid", "paid": True, "currency": "usd",
            "amount_paid": 2900, "amount_remaining": 0,
            "lines": {"data": [{"amount": 2900, "quantity": 1, "price": deepcopy(self.subscription["items"]["data"][0]["price"])}]}}
        for name, value in [("Subscription.retrieve", self.subscription), ("Invoice.retrieve", self.invoice)]:
            patcher = patch("stripe." + name, return_value=value)
            setattr(self, name.split(".")[0].lower() + "_retrieve", patcher.start())
            self.addCleanup(patcher.stop)

    def post(self, event_id="evt_email", kind="customer.subscription.updated", obj=None, execute=True):
        event = {"id": event_id, "livemode": False, "type": kind,
                 "data": {"object": obj if obj is not None else self.subscription}}
        payload = json.dumps(event).encode()
        timestamp = str(int(time.time()))
        signature = hmac.new(settings.STRIPE_WEBHOOK_SECRET.encode(), timestamp.encode() + b"." + payload, hashlib.sha256).hexdigest()
        with self.captureOnCommitCallbacks(execute=execute):
            return self.client.post(reverse("payments:webhook"), payload, content_type="application/json", HTTP_STRIPE_SIGNATURE=f"t={timestamp},v1={signature}")

    def test_paid_confirmation_has_plan_price_and_amount(self):
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Premium", mail.outbox[0].body)
        self.assertIn("$29.00 USD/month", mail.outbox[0].body)
        self.assertIn("Amount paid: $29.00 USD", mail.outbox[0].body)
        self.assertEqual(BillingEmail.objects.get().status, "sent")

    def test_pro_price(self):
        self.subscription["items"]["data"][0]["price"]["unit_amount"] = 5900
        self.invoice["amount_paid"] = 5900
        self.invoice["lines"]["data"][0]["price"]["unit_amount"] = 5900
        self.post()
        self.assertIn("Pro", mail.outbox[0].body)
        self.assertIn("$59.00 USD/month", mail.outbox[0].body)

    def test_historical_invoice_uses_billed_plan(self):
        self.subscription["items"]["data"][0]["price"]["unit_amount"] = 5900
        self.post(kind="invoice.paid", obj=self.invoice)
        self.assertIn("Premium", mail.outbox[0].body)
        self.assertNotIn("Pro", mail.outbox[0].body)

    def test_modern_invoice_price_reference(self):
        line = self.invoice["lines"]["data"][0]
        price = line.pop("price")
        line["pricing"] = {"price_details": {"price": "price_premium"}}
        with patch("stripe.Price.retrieve", return_value=price) as retrieve:
            self.post()
        retrieve.assert_called_once_with("price_premium", api_key=settings.STRIPE_SECRET_KEY)
        self.assertIn("Premium", mail.outbox[0].body)

    def test_renewal_gets_one_new_receipt(self):
        self.post()
        self.invoice["id"] = "in_renewal"
        self.subscription["latest_invoice"] = "in_renewal"
        self.post("evt_renewal")
        self.post("evt_renewal_duplicate")
        self.assertEqual(len(mail.outbox), 2)

    def test_pending_recovery_command_does_not_resend(self):
        from django.core.management import call_command
        self.post(execute=False)
        call_command("send_pending_billing_emails")
        call_command("send_pending_billing_emails")
        self.assertEqual(len(mail.outbox), 1)

    def test_zero_backend_acceptance_is_failed(self):
        with patch("ai_assistant.payments.emails.send_mail", return_value=0):
            self.post()
        self.assertEqual(BillingEmail.objects.get().status, "failed")

    def test_duplicate_event_and_distinct_events_same_invoice(self):
        self.post()
        self.post()
        self.post("evt_other", "invoice.paid", self.invoice)
        self.post("evt_succeeded", "invoice.payment_succeeded", self.invoice)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(BillingEmail.objects.count(), 1)

    def test_failed_or_unpaid_invoice_never_sends_success(self):
        for n, changes in enumerate([{"status": "open", "paid": False}, {"amount_paid": 0}, {"amount_remaining": 100}, {"currency": "eur"}]):
            original = deepcopy(self.invoice)
            self.invoice.update(changes)
            self.post(f"evt_bad_{n}")
            self.invoice.clear()
            self.invoice.update(original)
        self.post("evt_failed", "invoice.payment_failed", self.invoice)
        self.assertEqual(len(mail.outbox), 0)

    def test_active_subscription_without_paid_invoice_sends_nothing(self):
        self.subscription["latest_invoice"] = None
        self.post()
        self.assertEqual(len(mail.outbox), 0)

    def test_event_claim_is_not_authoritative(self):
        event_invoice = deepcopy(self.invoice)
        self.invoice.update(status="open", paid=False)
        self.post(kind="invoice.paid", obj=event_invoice)
        self.assertEqual(len(mail.outbox), 0)

    def test_invoice_parent_subscription_format(self):
        self.invoice.pop("subscription")
        self.invoice["parent"] = {"subscription_details": {"subscription": "sub_payer"}}
        self.assertEqual(self.post(kind="invoice.paid", obj=self.invoice).status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    def test_cancellation_date_and_duplicate_suppression(self):
        self.subscription.update(latest_invoice=None, cancel_at_period_end=True, canceled_at=1900000000)
        self.post()
        self.post("evt_again")
        self.subscription.update(status="canceled", cancel_at_period_end=False, ended_at=2000000000)
        self.post("evt_deleted", "customer.subscription.deleted")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Paid access continues through May 18, 2033 at 03:33 UTC", mail.outbox[0].body)

    def test_cancellation_unknown_end_is_honest(self):
        self.subscription.update(latest_invoice=None, status="canceled", current_period_end=None)
        self.post()
        self.assertIn("end date is not available", mail.outbox[0].body)

    def test_cancellation_can_send_without_payment_success(self):
        self.invoice.update(status="open", paid=False)
        self.subscription["cancel_at_period_end"] = True
        self.post()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("cancellation", mail.outbox[0].subject)

    def test_bad_invoice_owner_or_mode_rolls_back(self):
        for field, value in [("customer", "cus_other"), ("subscription", "sub_other"), ("livemode", True)]:
            original = self.invoice[field]
            self.invoice[field] = value
            self.assertEqual(self.post().status_code, 500)
            self.assertFalse(StripeEvent.objects.exists())
            self.invoice[field] = original
        self.assertEqual(len(mail.outbox), 0)

    def test_provider_retrieval_failure_is_retryable_without_email(self):
        self.invoice_retrieve.side_effect = RuntimeError("private")
        self.assertEqual(self.post().status_code, 500)
        self.assertFalse(StripeEvent.objects.exists())
        self.assertFalse(BillingEmail.objects.exists())
        self.invoice_retrieve.side_effect = None
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(len(mail.outbox), 1)

    def test_smtp_failure_does_not_reprocess_payment_or_retry_delivery(self):
        with patch("ai_assistant.payments.emails.send_mail", side_effect=RuntimeError("secret")) as send:
            self.assertEqual(self.post().status_code, 200)
            self.post()
            self.post("evt_retry")
        send.assert_called_once()
        self.assertEqual(BillingEmail.objects.get().status, "failed")
        self.assertTrue(StripeEvent.objects.exists())

    def test_deferred_delivery_and_durable_claim(self):
        self.post(execute=False)
        self.assertEqual(len(mail.outbox), 0)
        notice = BillingEmail.objects.get()
        self.assertEqual(notice.status, "pending")
        deliver(notice.pk)
        deliver(notice.pk)
        self.assertEqual(len(mail.outbox), 1)

    def test_rollback_discards_notification_and_callback(self):
        with self.captureOnCommitCallbacks(execute=True):
            try:
                with transaction.atomic():
                    queue("test", self.user.profile, "Test", "Test")
                    raise RuntimeError()
            except RuntimeError:
                pass
        self.assertFalse(BillingEmail.objects.exists())
        self.assertEqual(len(mail.outbox), 0)





