"""Billing lifecycle and durable duplicate-checkout regression tests."""
from copy import deepcopy
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch

import stripe
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import CheckoutAttempt
from .webhooks import update_profile_from_subscription


@override_settings(STRIPE_PUBLIC_KEY="pk_test_placeholder")
class BillingReconciliationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="lifecycle")
        self.client.force_login(self.user)
        self.profile = self.user.profile
        self.billing = reverse("payments:billing")
        self.checkout_url = reverse("payments:create_checkout_session")
        self.subscriptions = []
        self.sessions = []
        self.listing = self.mock("Subscription.list")
        self.listing.side_effect = lambda **kw: SimpleNamespace(
            auto_paging_iter=lambda: iter(self.subscriptions))
        self.session_list = self.mock("checkout.Session.list")
        self.session_list.side_effect = lambda **kw: SimpleNamespace(
            auto_paging_iter=lambda: iter(self.sessions))
        self.customer = self.mock("Customer.create")
        self.customer.return_value = SimpleNamespace(id="cus_owner")
        self.create = self.mock("checkout.Session.create")
        self.create.return_value = SimpleNamespace(id="cs_owner")
        self.session_retrieve = self.mock("checkout.Session.retrieve")
        self.session_retrieve.return_value = {"id": "cs_owner", "customer": "cus_owner", "status": "open"}
        self.retrieve = self.mock("Subscription.retrieve")
        self.modify = self.mock("Subscription.modify")

    def mock(self, name):
        patcher = patch("stripe." + name)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def subscription(self, status="active", amount=2900):
        return {"id": "sub_owner", "customer": "cus_owner", "livemode": False,
            "status": status, "cancel_at_period_end": True,
            "metadata": {"user_id": str(self.user.pk)},
            "collection_method": "charge_automatically", "latest_invoice": {"status": "paid"},
            "items": {"data": [{"id": "si_owner", "quantity": 1,
                "current_period_end": int((timezone.now() + timedelta(days=10)).timestamp()),
                "price": {"currency": "usd", "unit_amount": amount,
                    "recurring": {"interval": "month"}}}]}}

    def save_link(self, status="active"):
        self.profile.stripe_customer_id = "cus_owner"
        self.profile.stripe_subscription_id = "sub_owner"
        self.profile.stripe_subscription_status = status
        self.profile.subscription_cancel_at_period_end = True
        self.profile.save()

    def checkout(self, plan="premium"):
        return self.client.post(self.checkout_url, {"plan": plan})

    def assert_choices(self, response):
        self.assertContains(response, "Choose Premium")
        self.assertContains(response, "Choose Pro")
        self.assertNotContains(response, "Cancellation scheduled")

    def test_free_with_orphan_cancellation_flag_shows_both_actions(self):
        self.profile.subscription_cancel_at_period_end = True
        self.profile.subscription_ends_at = timezone.now() + timedelta(days=10)
        self.profile.save()
        self.assert_choices(self.client.get(self.billing))
        self.profile.refresh_from_db()
        self.assertFalse(self.profile.subscription_cancel_at_period_end)
        self.assertIsNone(self.profile.subscription_ends_at)
        self.assertEqual(self.checkout().status_code, 200)

    def test_stale_nonterminal_link_missing_from_customer_is_cleared(self):
        self.save_link()
        self.assert_choices(self.client.get(self.billing))
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.stripe_subscription_id)
        self.assertFalse(self.profile.subscription_cancel_at_period_end)
        self.assertEqual(self.checkout("pro").status_code, 200)

    def test_terminal_stripe_subscription_allows_fresh_checkout(self):
        for status in ["canceled", "incomplete_expired"]:
            with self.subTest(status=status):
                self.save_link()
                self.subscriptions = [self.subscription(status)]
                self.assert_choices(self.client.get(self.billing))
                self.profile.refresh_from_db()
                self.assertFalse(self.profile.subscription_cancel_at_period_end)
                self.assertFalse(self.profile.is_subscribed)
                self.assertEqual(self.checkout().status_code, 200)
                CheckoutAttempt.objects.all().delete()

    def test_checkout_refreshes_terminal_state_without_visiting_billing(self):
        self.save_link()
        self.subscriptions = [self.subscription("canceled")]
        self.assertEqual(self.checkout("pro").status_code, 200)
        self.assertEqual(self.create.call_args.kwargs["line_items"][0]["price_data"]["unit_amount"], 5900)

    def test_active_scheduled_cancel_restores_paid_plan_and_upgrade(self):
        self.save_link()
        self.subscriptions = [self.subscription()]
        response = self.client.get(self.billing)
        self.assertContains(response, "Access through")
        self.assertContains(response, "Upgrade to Pro")
        self.assertNotContains(response, "Choose Premium")
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.plan, "premium")
        self.assertTrue(self.profile.has_paid_plan)
        self.assertEqual(self.checkout("pro").status_code, 409)
        self.create.assert_not_called()

    def test_known_end_enforced_at_exact_time_even_without_webhook(self):
        sub = self.subscription()
        update_profile_from_subscription(self.profile, sub)
        end = self.profile.subscription_ends_at
        with patch("django.utils.timezone.now", return_value=end - timedelta(seconds=1)):
            self.assertTrue(self.profile.has_paid_plan)
        with patch("django.utils.timezone.now", return_value=end):
            self.assertFalse(self.profile.has_paid_plan)
            from ai_assistant.accounts.plan_utils import get_plan_config
            from django.conf import settings
            self.assertEqual(get_plan_config(self.profile), settings.AI_PLAN_CONFIG["free"])
            update_profile_from_subscription(self.profile, sub)
            self.assertEqual(self.profile.plan, "free")

    def test_genuine_nonterminal_states_and_unknown_price_block_checkout(self):
        self.save_link("canceled")
        for status in ["active", "trialing", "past_due", "unpaid", "incomplete", "paused", "unknown"]:
            self.subscriptions = [self.subscription(status, amount=1)]
            with self.subTest(status=status):
                self.assertEqual(self.checkout().status_code, 409)
        self.create.assert_not_called()

    def test_customer_inventory_finds_different_current_subscription(self):
        self.save_link("canceled")
        sub = self.subscription()
        sub["id"] = "sub_new"
        self.subscriptions = [sub]
        self.assertEqual(self.checkout().status_code, 409)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.stripe_subscription_id, "sub_new")
        self.create.assert_not_called()

    def test_multiple_subscriptions_require_support(self):
        self.save_link()
        second = self.subscription()
        second["id"] = "sub_second"
        self.subscriptions = [self.subscription(), second]
        self.assertEqual(self.checkout().status_code, 500)
        self.create.assert_not_called()

    def test_provider_failure_does_not_clear_link_or_enable_checkout(self):
        self.save_link()
        self.listing.side_effect = RuntimeError("private-provider-detail")
        response = self.client.get(self.billing)
        self.assertFalse(response.context["can_checkout"])
        self.assertNotContains(response, "private-provider-detail")
        self.assertEqual(self.checkout().status_code, 500)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.stripe_subscription_id, "sub_owner")
        self.create.assert_not_called()

    def test_wrong_owner_customer_and_mode_fail_closed(self):
        self.save_link()
        for field, value in [("customer", "cus_other"), ("metadata", {"user_id": "99999"}), ("livemode", True)]:
            sub = self.subscription()
            sub[field] = value
            self.subscriptions = [sub]
            self.assertEqual(self.checkout().status_code, 500)
        self.create.assert_not_called()

    def test_repeated_tabs_reuse_one_session_and_other_plan_is_blocked(self):
        self.assertEqual(self.checkout().status_code, 200)
        self.assertEqual(self.checkout().json()["id"], "cs_owner")
        self.assertEqual(self.checkout("pro").status_code, 409)
        self.create.assert_called_once()
        self.customer.assert_called_once()
        self.assertEqual(CheckoutAttempt.objects.count(), 1)

    def test_uncertain_create_retries_exact_saved_intent(self):
        self.create.side_effect = stripe.error.APIConnectionError("private-provider-detail")
        self.assertEqual(self.checkout().status_code, 500)
        first = deepcopy(self.create.call_args.kwargs)
        self.assertEqual(self.checkout().status_code, 500)
        self.assertEqual(self.create.call_args.kwargs, first)
        self.assertEqual(CheckoutAttempt.objects.count(), 1)

    def test_uncertain_response_can_recover_session_from_inventory(self):
        self.create.side_effect = stripe.error.APIConnectionError("private-provider-detail")
        self.checkout()
        attempt = CheckoutAttempt.objects.get()
        self.sessions = [{"id": "cs_owner", "customer": "cus_owner", "mode": "subscription",
            "status": "open", "metadata": {"attempt": str(attempt.key)}}]
        self.assertEqual(self.checkout().status_code, 409)
        self.assertEqual(self.checkout().status_code, 200)
        self.create.assert_called_once()

    def test_old_unknown_attempt_cannot_outlive_stripe_idempotency(self):
        self.create.side_effect = RuntimeError("uncertain")
        self.checkout()
        CheckoutAttempt.objects.update(started_at=timezone.now() - timedelta(hours=24))
        self.assertEqual(self.checkout().status_code, 409)
        self.create.assert_called_once()

    def test_expired_session_can_be_replaced_after_provider_confirmation(self):
        self.checkout()
        old_key = CheckoutAttempt.objects.get().key
        self.session_retrieve.return_value["status"] = "expired"
        self.assertEqual(self.checkout("pro").status_code, 409)
        self.assertEqual(self.checkout("pro").status_code, 200)
        self.assertNotEqual(CheckoutAttempt.objects.get().key, old_key)

    def test_completed_session_blocks_until_terminal_subscription_confirmed(self):
        self.checkout()
        self.session_retrieve.return_value.update(status="complete", subscription="sub_owner")
        self.retrieve.return_value = self.subscription()
        self.assertEqual(self.checkout().status_code, 409)
        self.create.assert_called_once()
        self.retrieve.return_value = self.subscription("canceled")
        self.assertEqual(self.checkout().status_code, 409)
        self.assertEqual(self.checkout("pro").status_code, 200)

    def test_legacy_open_checkout_blocks_new_session(self):
        self.sessions = [{"mode": "subscription", "status": "open"}]
        self.assertEqual(self.checkout().status_code, 409)
        self.create.assert_not_called()

    def test_past_due_copy_explains_open_contract_without_promising_access(self):
        self.save_link()
        self.subscriptions = [self.subscription("past_due")]
        response = self.client.get(self.billing)
        self.assertContains(response, "Your subscription is still open (past_due)")
        self.assertNotContains(response, "Access through")
        self.assertNotContains(response, "Choose Premium")
        self.assertNotContains(response, "Upgrade to Pro")

    def test_partial_inventory_failure_preserves_saved_state(self):
        self.save_link()
        def pages():
            yield self.subscription("canceled")
            raise RuntimeError("Next page unavailable")
        self.listing.side_effect = lambda **kw: SimpleNamespace(auto_paging_iter=pages)
        self.assertEqual(self.checkout().status_code, 500)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.stripe_subscription_status, "active")
        self.create.assert_not_called()

    def test_missing_current_link_still_checks_all_customer_subscriptions(self):
        self.profile.stripe_customer_id = "cus_owner"
        self.profile.save()
        self.subscriptions = [self.subscription("unpaid")]
        self.assertEqual(self.checkout().status_code, 409)
        self.listing.assert_called_with(customer="cus_owner", status="all", limit=100,
            api_key="sk_test_placeholder")
        self.create.assert_not_called()

    def test_expired_entitlement_cannot_be_upgraded(self):
        sub = self.subscription()
        update_profile_from_subscription(self.profile, sub)
        token = self.client.get(self.billing).context["upgrade_token"]
        self.retrieve.return_value = sub
        with patch("django.utils.timezone.now", return_value=self.profile.subscription_ends_at):
            self.client.post(reverse("payments:upgrade_subscription"), {"upgrade_token": token})
        self.modify.assert_not_called()

    def test_checkout_rejects_unsafe_methods_and_has_private_response(self):
        for method in [self.client.get, self.client.put, self.client.delete]:
            self.assertEqual(method(self.checkout_url).status_code, 405)
        self.create.assert_not_called()
        self.assertIn("no-store", self.checkout()["Cache-Control"])

    def test_blocked_checkout_does_not_leave_an_intent_that_blocks_future_plans(self):
        self.save_link()
        self.subscriptions = [self.subscription("past_due")]
        self.assertEqual(self.checkout("premium").status_code, 409)
        self.assertFalse(CheckoutAttempt.objects.exists())
        self.subscriptions = [self.subscription("canceled")]
        self.assertEqual(self.checkout("pro").status_code, 200)

    def test_billing_missing_link_discovers_nonterminal_subscription(self):
        self.profile.stripe_customer_id = "cus_owner"
        self.profile.save()
        self.subscriptions = [self.subscription("unpaid")]
        response = self.client.get(self.billing)
        self.assertFalse(response.context["can_checkout"])
        self.assertContains(response, "Your subscription is still open (unpaid)")
        self.create.assert_not_called()

    def test_free_stale_end_without_cancel_flag_is_reconciled(self):
        self.save_link("past_due")
        self.profile.subscription_cancel_at_period_end = False
        self.profile.subscription_ends_at = timezone.now() + timedelta(days=10)
        self.profile.save()
        self.subscriptions = [self.subscription("canceled")]
        self.assert_choices(self.client.get(self.billing))
        self.profile.refresh_from_db()
        self.assertIsNone(self.profile.subscription_ends_at)

    def test_nonterminal_without_cancellation_explains_payment_resolution(self):
        for status in ["past_due", "unpaid", "incomplete", "paused"]:
            with self.subTest(status=status):
                sub = self.subscription(status)
                sub["cancel_at_period_end"] = False
                update_profile_from_subscription(self.profile, sub)
                response = self.client.get(self.billing)
                self.assertContains(response, "Paid access is currently unavailable")
                self.assertContains(response, "Your subscription is still open (" + status + ")")
                self.assertNotContains(response, "Choose Premium")
                self.assertNotContains(response, "Upgrade to Pro")

    def test_terminal_stale_paid_profile_clears_flags_on_billing(self):
        self.save_link("canceled")
        self.profile.plan = "premium"
        self.profile.is_subscribed = True
        self.profile.save()
        self.subscriptions = [self.subscription("canceled")]
        self.assert_choices(self.client.get(self.billing))
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.plan, "free")
        self.assertFalse(self.profile.is_subscribed)
        self.assertFalse(self.profile.subscription_cancel_at_period_end)

