"""Stateful provider simulations for continuation, scheduling, and lost replies."""
from copy import deepcopy
from datetime import timedelta
import json
from types import SimpleNamespace
from unittest.mock import patch

import stripe
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import SubscriptionChange, SubscriptionRecovery, StripeEvent
from .webhooks import update_profile_from_subscription


class ContinuationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("continuation-owner")
        self.client.force_login(self.user)
        self.billing = reverse("payments:billing")
        self.sub = {"id": "sub_owner", "customer": "cus_owner", "livemode": False,
            "status": "active", "collection_method": "charge_automatically",
            "cancel_at_period_end": False, "latest_invoice": {"id": "in_paid", "status": "paid"},
            "metadata": {"user_id": str(self.user.pk), "plan": "pro"},
            "items": {"data": [{"id": "si_owner", "quantity": 1,
                "current_period_start": 1897300000, "current_period_end": 1900000000,
                "price": {"id": "price_pro", "currency": "usd", "unit_amount": 2499,
                    "recurring": {"interval": "month", "interval_count": 1}}}]}}
        self.schedule = None
        self.calls = {}
        self.retrieve = self.mock("Subscription.retrieve", side_effect=lambda *a, **kw: deepcopy(self.sub))
        self.sub_list = self.mock("Subscription.list", side_effect=lambda **kw: self.page([deepcopy(self.sub)]))
        self.modify = self.mock("Subscription.modify", side_effect=self.modify_subscription)
        self.product = self.mock("Product.create", return_value=SimpleNamespace(id="prod_target"))
        self.price = self.mock("Price.create", return_value=SimpleNamespace(id="price_target"))
        self.create_schedule = self.mock("SubscriptionSchedule.create", side_effect=self.new_schedule)
        self.read_schedule = self.mock("SubscriptionSchedule.retrieve", side_effect=lambda *a, **kw: deepcopy(self.schedule))
        self.configure = self.mock("SubscriptionSchedule.modify", side_effect=self.configure_schedule)
        self.invoices = self.mock("Invoice.list", return_value=self.page([]))
        self.invoice_items = self.mock("InvoiceItem.list", return_value=self.page([]))
        self.sessions = self.mock("checkout.Session.list", return_value=self.page([]))
        self.checkout = self.mock("checkout.Session.create")
        self.mock("Webhook.construct_event")
        self.save()

    @staticmethod
    def page(values):
        return SimpleNamespace(auto_paging_iter=lambda: iter(values))

    def mock(self, name, **kwargs):
        p = patch("stripe." + name, **kwargs)
        result = p.start()
        self.addCleanup(p.stop)
        return result

    def save(self):
        update_profile_from_subscription(self.user.profile, self.sub)

    def cancel(self):
        self.sub.update(cancel_at_period_end=True, cancel_at=1900000000)
        self.save()

    def premium(self):
        self.sub["items"]["data"][0]["price"].update(id="price_premium", unit_amount=1299)
        self.save()

    def token(self, action):
        return self.client.get(self.billing).context[action + "_token"]

    def post(self, action, token=None):
        return self.client.post(reverse("payments:" + action + "_subscription"),
            {"change_token": token or self.token(action)}, follow=True)

    def retry(self):
        page = self.client.get(self.billing)
        change = SubscriptionChange.objects.get()
        return self.post(change.action, page.context["retry_token"])

    def modify_subscription(self, sid, **kwargs):
        self.assertEqual(sid, self.sub["id"])
        self.assertTrue(SubscriptionChange.objects.exists())
        if "items" in kwargs:
            self.sub["items"]["data"][0]["price"].update(id="price_target", unit_amount=2499)
        if kwargs.get("cancel_at_period_end") is False:
            self.sub.update(cancel_at_period_end=False, cancel_at=None)
        return deepcopy(self.sub)

    def new_schedule(self, **kwargs):
        key = kwargs["idempotency_key"]
        if key not in self.calls:
            self.schedule = {"id": "sched_owner", "subscription": self.sub["id"],
                "customer": "cus_owner", "livemode": False, "status": "active",
                "end_behavior": "release", "metadata": {}, "phases": [{
                    "start_date": 1897300000, "end_date": 1900000000,
                    "items": [{"price": "price_pro", "quantity": 1}]}]}
            self.sub["schedule"] = self.schedule["id"]
            self.calls[key] = deepcopy(self.schedule)
        return deepcopy(self.calls[key])

    def configure_schedule(self, sid, **kwargs):
        self.assertEqual(sid, self.schedule["id"])
        self.schedule.update(phases=deepcopy(kwargs["phases"]),
            end_behavior=kwargs["end_behavior"], metadata=kwargs["metadata"])
        return deepcopy(self.schedule)

    def test_canceled_pro_downgrade_continues_and_preserves_pro_until_boundary(self):
        self.cancel()
        response = self.post("downgrade")
        self.assertContains(response, "Pending downgrade: Premium")
        self.assertContains(response, "March 17, 2030")
        self.assertNotContains(response, "Cancellation scheduled.")
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.plan, "pro")
        self.assertFalse(self.user.profile.subscription_cancel_at_period_end)
        self.assertEqual(SubscriptionChange.objects.get().status, "scheduled")
        self.assertEqual(self.configure.call_args.kwargs["phases"][0]["items"][0]["price"], "price_pro")
        self.assertEqual(self.configure.call_args.kwargs["phases"][1]["start_date"], 1900000000)
        self.assertEqual(self.configure.call_args.kwargs["phases"][1]["iterations"], 1)
        self.assertEqual(self.configure.call_args.kwargs["end_behavior"], "release")
        self.assertNotIn("items", self.modify.call_args.kwargs)
        self.checkout.assert_not_called()

    def test_uncanceled_downgrade_does_not_modify_current_subscription(self):
        self.post("downgrade")
        self.modify.assert_not_called()
        self.assertEqual(self.sub["items"]["data"][0]["price"]["unit_amount"], 2499)

    def test_resume_same_plan_no_charge_or_boundary_change(self):
        for plan in ("pro", "premium"):
            with self.subTest(plan=plan):
                if plan == "premium":
                    self.premium()
                self.cancel()
                self.post("resume")
                self.user.profile.refresh_from_db()
                self.assertEqual(self.user.profile.plan, plan)
                self.assertEqual(int(self.user.profile.subscription_current_period_end.timestamp()), 1900000000)
                self.assertIsNone(self.user.profile.subscription_ends_at)
                self.assertNotIn("items", self.modify.call_args.kwargs)
                self.assertEqual(self.modify.call_args.kwargs["proration_behavior"], "none")
        self.create_schedule.assert_not_called()
        self.product.assert_not_called()

    def test_canceled_premium_upgrade_clears_cancellation_atomically(self):
        self.premium()
        self.cancel()
        self.post("upgrade")
        args = self.modify.call_args.kwargs
        self.assertFalse(args["cancel_at_period_end"])
        self.assertEqual(args["payment_behavior"], "error_if_incomplete")
        self.assertEqual(args["billing_cycle_anchor"], "unchanged")
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.plan, "pro")
        self.assertFalse(self.user.profile.subscription_cancel_at_period_end)

    def test_failed_upgrade_payment_keeps_canceled_premium(self):
        self.premium()
        self.cancel()
        self.modify.side_effect = stripe.error.CardError("private-detail", "card", "declined")
        response = self.post("upgrade")
        self.assertContains(response, "Payment could not be completed")
        self.assertNotContains(response, "private-detail")
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.plan, "premium")
        self.assertTrue(self.user.profile.subscription_cancel_at_period_end)
        self.assertEqual(SubscriptionChange.objects.get().status, "failed")

    def test_lost_schedule_creation_response_recovers_same_schedule(self):
        def lost(**kwargs):
            self.new_schedule(**kwargs)
            raise stripe.error.APIConnectionError("lost")
        self.create_schedule.side_effect = lost
        self.post("downgrade")
        key = self.create_schedule.call_args.kwargs["idempotency_key"]
        self.create_schedule.side_effect = self.new_schedule
        self.retry()
        self.assertEqual(self.create_schedule.call_args.kwargs["idempotency_key"], key)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(SubscriptionChange.objects.get().status, "scheduled")

    def test_definitive_decline_allows_new_payment_attempt_after_correction(self):
        self.premium()
        self.cancel()
        self.modify.side_effect = stripe.error.CardError("declined", "card", "declined")
        self.post("upgrade")
        first_key = self.modify.call_args.kwargs["idempotency_key"]
        self.modify.side_effect = self.modify_subscription
        self.post("upgrade")
        self.assertNotEqual(self.modify.call_args.kwargs["idempotency_key"], first_key)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.plan, "pro")
        self.assertFalse(self.user.profile.subscription_cancel_at_period_end)

    def test_lost_resume_response_does_not_repeat_provider_write(self):
        self.cancel()
        def lost(*args, **kwargs):
            self.modify_subscription(*args, **kwargs)
            raise stripe.error.APIConnectionError("lost")
        self.modify.side_effect = lost
        self.post("resume")
        self.retry()
        self.modify.assert_called_once()
        self.assertEqual(SubscriptionChange.objects.get().status, "complete")

    def test_stale_cancellation_consent_cannot_clear_new_cancellation(self):
        old = self.token("downgrade")
        self.cancel()
        self.post("downgrade", old)
        self.modify.assert_not_called()
        self.create_schedule.assert_not_called()

    def test_failed_continuation_does_not_attach_schedule(self):
        self.cancel()
        self.modify.side_effect = stripe.error.APIConnectionError("lost")
        self.post("downgrade")
        self.create_schedule.assert_not_called()
        self.assertTrue(self.sub["cancel_at_period_end"])

    def test_ended_subscription_does_not_promise_pending_pro_access(self):
        self.post("downgrade")
        self.sub.update(status="canceled", ended_at=1899999000)
        self.event()
        self.assertEqual(SubscriptionChange.objects.get().status, "removed")
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.plan, "free")

    def test_foreign_schedule_response_cannot_be_adopted(self):
        def foreign(**kwargs):
            result = self.new_schedule(**kwargs)
            result["customer"] = "cus_other"
            return result
        self.create_schedule.side_effect = foreign
        self.post("downgrade")
        self.configure.assert_not_called()
        self.assertEqual(SubscriptionChange.objects.get().schedule_id, "")

    def test_lost_schedule_update_response_retries_identical_parameters(self):
        def lost(*args, **kwargs):
            self.configure_schedule(*args, **kwargs)
            raise stripe.error.APIConnectionError("lost")
        self.configure.side_effect = lost
        self.post("downgrade")
        first = self.configure.call_args
        self.configure.side_effect = self.configure_schedule
        self.retry()
        self.assertEqual(self.configure.call_args, first)
        self.create_schedule.assert_called_once()
        self.assertEqual(SubscriptionChange.objects.get().status, "scheduled")

    def test_partial_downgrade_reports_cancellation_already_cleared(self):
        self.cancel()
        self.price.side_effect = RuntimeError("private-detail")
        response = self.post("downgrade")
        self.assertContains(response, "Cancellation may already")
        self.assertNotContains(response, "Pending downgrade: Premium")
        self.assertFalse(self.sub["cancel_at_period_end"])
        self.price.side_effect = None
        self.retry()
        self.assertEqual(SubscriptionChange.objects.get().status, "scheduled")

    def test_separate_tabs_and_retries_do_not_create_duplicate_schedules(self):
        first, second = self.token("downgrade"), self.token("downgrade")
        self.post("downgrade", first)
        self.post("downgrade", second)
        self.retry()
        self.create_schedule.assert_called_once()
        self.configure.assert_called_once()

    def test_cancellation_conflict_is_displayed_and_never_silently_cleared(self):
        self.post("downgrade")
        self.sub.update(cancel_at_period_end=True, cancel_at=1900000000)
        response = self.client.get(self.billing + "?sync=1")
        self.assertContains(response, "conflicts with the current Stripe state")
        self.assertContains(response, "Cancellation scheduled")
        self.assertNotContains(response, "Pending downgrade: Premium")
        self.assertEqual(SubscriptionChange.objects.get().status, "conflict")
        self.post("resume")
        self.modify.assert_not_called()

    def test_conflicting_intent_cannot_replace_uncertain_operation(self):
        self.cancel()
        stale_resume = self.token("resume")
        self.configure.side_effect = RuntimeError("lost")
        self.post("downgrade")
        key = SubscriptionChange.objects.get().key
        self.post("resume", stale_resume)
        self.assertEqual(SubscriptionChange.objects.get().key, key)
        self.assertEqual(SubscriptionChange.objects.get().action, "downgrade")

    def test_retry_window_expiry_requires_support_without_mutation(self):
        self.configure.side_effect = RuntimeError("lost")
        self.post("downgrade")
        SubscriptionChange.objects.update(started_at=timezone.now() - timedelta(hours=24))
        self.configure.reset_mock()
        self.retry()
        self.configure.assert_not_called()

    def test_multiple_subscriptions_block_every_action(self):
        extra = deepcopy(self.sub)
        extra["id"] = "sub_duplicate"
        self.sub_list.return_value = self.page([self.sub, extra])
        self.sub_list.side_effect = None
        self.cancel()
        self.post("downgrade")
        self.post("resume")
        self.premium()
        self.post("upgrade")
        self.modify.assert_not_called()
        self.create_schedule.assert_not_called()

    def test_outstanding_invoices_and_open_checkout_block_changes(self):
        for field, record in ((self.invoices, {"id": "in_open"}),
                (self.invoice_items, {"id": "ii_pending"}),
                (self.sessions, {"mode": "subscription", "status": "open"})):
            field.return_value = self.page([record])
            self.post("downgrade")
            field.return_value = self.page([])
        self.assertFalse(SubscriptionChange.objects.exists())
        self.create_schedule.assert_not_called()

    def test_unsupported_provider_states_fail_closed(self):
        original = deepcopy(self.sub)
        for field, value in (("schedule", "foreign_schedule"), ("pause_collection", {"behavior": "void"}),
                ("pending_update", {"expires_at": 1900000000}), ("status", "unpaid"),
                ("latest_invoice", {"status": "open"}), ("cancel_at", 1899999999),
                ("discounts", ["di_custom"]), ("automatic_tax", {"enabled": True})):
            self.sub = deepcopy(original)
            self.sub[field] = value
            self.post("downgrade")
        self.create_schedule.assert_not_called()
        self.modify.assert_not_called()

    def test_owner_mode_item_and_boundary_validation(self):
        original = deepcopy(self.sub)
        for field, value in (("customer", "cus_other"), ("livemode", True),
                ("metadata", {"user_id": "999"}), ("id", "sub_other")):
            self.sub = deepcopy(original)
            self.sub[field] = value
            self.post("downgrade")
        self.sub = deepcopy(original)
        self.sub["items"]["has_more"] = True
        self.post("downgrade")
        self.sub = deepcopy(original)
        self.sub["items"]["data"][0]["current_period_end"] = 1
        self.post("downgrade")
        self.create_schedule.assert_not_called()

    def test_login_methods_csrf_and_signed_action(self):
        for action in ("resume", "downgrade"):
            url = reverse("payments:" + action + "_subscription")
            self.assertEqual(Client().post(url).status_code, 302)
            self.assertEqual(self.client.get(url).status_code, 405)
            csrf = Client(enforce_csrf_checks=True)
            csrf.force_login(self.user)
            self.assertEqual(csrf.post(url).status_code, 403)
            self.post(action, "invalid")
        self.post("resume", self.token("downgrade"))
        self.modify.assert_not_called()
        self.create_schedule.assert_not_called()

    def test_pending_legacy_recovery_blocks_new_flow(self):
        SubscriptionRecovery.objects.create(profile=self.user.profile,
            source_subscription="sub_legacy", plan="pro")
        self.post("downgrade")
        self.create_schedule.assert_not_called()

    def event(self, kind="customer.subscription.updated", eid="evt_current"):
        obj = deepcopy(self.schedule if kind.startswith("subscription_schedule.") else self.sub)
        event = {"id": eid, "type": kind, "livemode": False, "data": {"object": obj}}
        with patch("ai_assistant.payments.webhooks.queue_subscription_emails") as emails:
            response = self.client.post(reverse("payments:webhook"), json.dumps(event), content_type="application/json")
            if kind.startswith("subscription_schedule."):
                emails.assert_not_called()
        return response

    def test_webhook_boundary_applies_actual_premium_price(self):
        self.post("downgrade")
        self.sub["items"]["data"][0]["price"].update(id="price_target", unit_amount=1299)
        self.sub["items"]["data"][0]["current_period_end"] = 1902678400
        self.assertEqual(self.event().status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.plan, "premium")
        self.assertEqual(SubscriptionChange.objects.get().status, "complete")
        self.assertEqual(self.event().status_code, 200)
        self.assertEqual(StripeEvent.objects.count(), 1)

    def test_failed_renewal_does_not_keep_pro_entitlement(self):
        self.post("downgrade")
        self.sub["status"] = "past_due"
        self.sub["items"]["data"][0]["price"].update(id="price_target", unit_amount=1299)
        self.event()
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.plan, "free")
        self.assertFalse(self.user.profile.has_paid_plan)

    def test_schedule_release_event_clears_pending_downgrade(self):
        self.post("downgrade")
        self.schedule.update(status="released", subscription=None, released_subscription=self.sub["id"])
        self.sub["schedule"] = None
        self.assertEqual(self.event("subscription_schedule.released").status_code, 200)
        self.assertEqual(SubscriptionChange.objects.get().status, "removed")
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.plan, "pro")

    def test_schedule_lookup_failure_rolls_back_webhook_and_retries(self):
        self.post("downgrade")
        self.read_schedule.side_effect = RuntimeError("lost")
        self.assertEqual(self.event("subscription_schedule.updated").status_code, 500)
        self.assertFalse(StripeEvent.objects.exists())
        self.read_schedule.side_effect = lambda *a, **kw: deepcopy(self.schedule)
        self.assertEqual(self.event("subscription_schedule.updated").status_code, 200)

    def test_external_schedule_edit_is_not_shown_as_confirmed(self):
        self.post("downgrade")
        self.schedule["phases"][1]["items"][0]["price"] = "price_unknown"
        self.event("subscription_schedule.updated")
        self.assertEqual(SubscriptionChange.objects.get().status, "conflict")
        self.assertNotContains(self.client.get(self.billing), "Pending downgrade: Premium")

    def test_real_sdk_objects_support_schedule_reconciliation(self):
        self.post("downgrade")
        self.read_schedule.side_effect = lambda *a, **kw: stripe.SubscriptionSchedule.construct_from(self.schedule, "test")
        self.retrieve.side_effect = lambda *a, **kw: stripe.Subscription.construct_from(self.sub, "test")
        self.assertEqual(self.event("subscription_schedule.updated").status_code, 200)
        self.assertEqual(SubscriptionChange.objects.get().status, "scheduled")
