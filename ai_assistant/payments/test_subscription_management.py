"""Regression coverage for existing-subscription changes and cancellation UI."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import stripe
from django.contrib.auth.models import User
from django.core import signing
from django.test import Client, TestCase
from django.urls import reverse

from .webhooks import update_profile_from_subscription


class SubscriptionManagementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="upgrade-owner")
        self.client.force_login(self.user)
        self.url = reverse("payments:upgrade_subscription")
        self.billing = reverse("payments:billing")
        self.subscription = {
            "id": "sub_owner", "customer": "cus_owner", "livemode": False,
            "status": "active", "collection_method": "charge_automatically",
            "latest_invoice": {"id": "in_paid", "status": "paid"},
            "metadata": {"user_id": str(self.user.pk), "plan": "premium"},
            "items": {"data": [{"id": "si_owner", "quantity": 1,
                "current_period_end": 1900000000,
                "price": {"id": "price_premium", "currency": "usd", "unit_amount": 1299,
                    "recurring": {"interval": "month"}}}]},
        }
        update_profile_from_subscription(self.user.profile, self.subscription)
        self.token = self.client.get(self.billing).context["upgrade_token"]
        self.retrieve = self.mock("stripe.Subscription.retrieve")
        self.retrieve.return_value = self.subscription
        self.list_subscriptions = self.mock("stripe.Subscription.list")
        self.list_subscriptions.side_effect = lambda **kwargs: SimpleNamespace(
            auto_paging_iter=lambda: iter([self.retrieve()]))
        self.modify = self.mock("stripe.Subscription.modify")
        self.product = self.mock("stripe.Product.create")
        self.product.return_value = SimpleNamespace(id="prod_pro")
        self.checkout = self.mock("stripe.checkout.Session.create")

    def mock(self, name):
        mocker = patch("ai_assistant.payments.views." + name)
        result = mocker.start()
        self.addCleanup(mocker.stop)
        return result

    def post(self, **extra):
        return self.client.post(self.url, {"upgrade_token": self.token, **extra})

    def pro(self):
        result = deepcopy(self.subscription)
        result["items"]["data"][0]["price"]["unit_amount"] = 2499
        return result

    def test_upgrade_replaces_item_prorates_and_reconciles_without_checkout(self):
        self.retrieve.side_effect = [self.subscription, self.pro()]
        response = self.post(subscription="sub_attacker", customer="cus_attacker", price=1, plan="free")
        self.assertEqual(response.status_code, 302)
        args, kwargs = self.modify.call_args
        self.assertEqual(args, ("sub_owner",))
        self.assertEqual(kwargs["api_key"], "sk_test_placeholder")
        self.assertEqual(kwargs["items"], [{"id": "si_owner", "quantity": 1,
            "price_data": {"currency": "usd", "unit_amount": 2499,
                "recurring": {"interval": "month"}, "product": "prod_pro"}}])
        self.assertEqual(kwargs["proration_behavior"], "always_invoice")
        self.assertEqual(kwargs["payment_behavior"], "error_if_incomplete")
        self.assertEqual(kwargs["billing_cycle_anchor"], "unchanged")
        self.assertEqual(kwargs["metadata"], {"plan": "pro", "user_id": str(self.user.pk)})
        self.assertNotIn("cancel_at_period_end", kwargs)
        self.assertNotIn("cancel_at", kwargs)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.plan, "pro")
        self.assertEqual(self.user.profile.stripe_subscription_id, "sub_owner")
        self.checkout.assert_not_called()

    def test_repeated_upgrade_uses_current_stripe_state_and_does_not_charge_again(self):
        self.retrieve.side_effect = [self.subscription, self.pro(), self.pro()]
        self.post()
        self.post()
        self.modify.assert_called_once()
        self.checkout.assert_not_called()

    def test_uncertain_provider_result_retries_same_idempotency_key(self):
        self.modify.side_effect = RuntimeError("private-provider-detail")
        self.post()
        first = self.modify.call_args.kwargs["idempotency_key"]
        self.post()
        self.assertEqual(self.modify.call_args.kwargs["idempotency_key"], first)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.plan, "premium")

    def test_failed_payment_preserves_premium_and_sanitizes_error(self):
        self.modify.side_effect = stripe.error.CardError("private-provider-detail", "card", "card_declined")
        response = self.client.post(self.url, {"upgrade_token": self.token}, follow=True)
        self.assertContains(response, "Payment could not be completed")
        self.assertNotContains(response, "private-provider-detail")
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.plan, "premium")
        self.checkout.assert_not_called()

    def test_security_login_methods_csrf_and_valid_csrf_form(self):
        self.assertEqual(Client().post(self.url).status_code, 302)
        for method in [self.client.get, self.client.put, self.client.delete]:
            self.assertEqual(method(self.url).status_code, 405)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(self.url, {"upgrade_token": self.token}).status_code, 403)
        self.modify.assert_not_called()
        response = csrf.get(self.billing)
        self.assertContains(response, 'action="' + self.url + '"')
        csrf.post(self.url, {"upgrade_token": response.context["upgrade_token"],
            "csrfmiddlewaretoken": csrf.cookies["csrftoken"].value})
        self.modify.assert_called_once()

    def test_invalid_expired_and_other_user_intents(self):
        for token in ["", "invalid", signing.dumps({"user": self.user.pk + 1,
                "subscription": "sub_owner"}, salt="billing-upgrade")]:
            self.client.post(self.url, {"upgrade_token": token})
        with patch("django.core.signing.time.time", return_value=1):
            expired = signing.dumps({"user": self.user.pk, "subscription": "sub_owner"}, salt="billing-upgrade")
        self.client.post(self.url, {"upgrade_token": expired})
        self.retrieve.assert_not_called()
        self.modify.assert_not_called()

    def test_wrong_subscription_customer_owner_and_mode_rejected(self):
        for field, value in [("id", "sub_other"), ("customer", "cus_other"),
                             ("metadata", {"user_id": "999999"}), ("livemode", True)]:
            with self.subTest(field=field):
                sub = deepcopy(self.subscription)
                sub[field] = value
                self.retrieve.return_value = sub
                self.post()
        self.modify.assert_not_called()
        self.product.assert_not_called()

    def test_ineligible_states_cannot_mutate_subscription(self):
        for field, value in [("status", "past_due"), ("status", "canceled"),
                ("status", "trialing"), ("collection_method", "send_invoice"),
                ("pending_update", {"expires_at": 1900000000}),
                ("latest_invoice", {"id": "in_open", "status": "open"}),
                ("latest_invoice", None),
                ("schedule", "sub_sched"), ("pause_collection", {"behavior": "void"})]:
            sub = deepcopy(self.subscription)
            sub[field] = value
            self.retrieve.return_value = sub
            self.post()
        sub = deepcopy(self.subscription)
        sub["items"]["data"][0]["price"]["unit_amount"] = 1
        self.retrieve.return_value = sub
        self.post()
        self.modify.assert_not_called()
        self.checkout.assert_not_called()

    def test_missing_key_or_customer_prevents_provider_mutation(self):
        with self.settings(STRIPE_SECRET_KEY=""):
            self.post()
        self.user.profile.stripe_customer_id = None
        self.user.profile.save()
        self.post()
        self.retrieve.assert_not_called()
        self.modify.assert_not_called()

    def test_scheduled_cancellation_survives_upgrade_and_blocks_duplicate_checkout(self):
        self.subscription["cancel_at_period_end"] = True
        self.subscription["cancel_at"] = 1900000000
        self.retrieve.side_effect = [self.subscription, self.pro()]
        self.post()
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.plan, "pro")
        self.assertTrue(self.user.profile.subscription_cancel_at_period_end)
        self.assertEqual(int(self.user.profile.subscription_ends_at.timestamp()), 1900000000)
        self.retrieve.side_effect = None
        self.retrieve.return_value = self.pro()
        self.assertEqual(self.client.post(reverse("payments:create_checkout_session"), {"plan": "pro"}).status_code, 409)
        self.checkout.assert_not_called()

    def test_cancel_dates_refresh_on_portal_return_and_resume_clears_date(self):
        self.subscription.update(cancel_at_period_end=True, canceled_at=1800000000)
        response = self.client.get(self.billing + "?sync=1")
        self.assertContains(response, "Access through")
        self.assertContains(response, "March 17, 2030")
        self.assertContains(response, "Upgrade to Pro")
        self.assertContains(response, "does not restart renewal")
        self.assertNotContains(response, "Next renewal:")
        self.user.profile.refresh_from_db()
        self.assertEqual(int(self.user.profile.subscription_ends_at.timestamp()), 1900000000)
        self.subscription["cancel_at_period_end"] = False
        self.client.get(self.billing + "?sync=1")
        self.user.profile.refresh_from_db()
        self.assertIsNone(self.user.profile.subscription_ends_at)

    def test_actual_end_overrides_future_period_and_requested_cancel_date(self):
        self.subscription.update(status="canceled", ended_at=1800000000,
            cancel_at=1900000000, canceled_at=1700000000)
        response = self.client.get(self.billing + "?sync=1")
        self.assertContains(response, "Subscription ended on")
        self.assertNotContains(response, "Access through")
        self.user.profile.refresh_from_db()
        self.assertEqual(int(self.user.profile.subscription_ends_at.timestamp()), 1800000000)
        self.assertEqual(self.user.profile.plan, "free")

    def test_explicit_cancel_date_legacy_period_end_and_unknown_date(self):
        self.subscription.update(cancel_at=1850000000, current_period_end=1900000100)
        update_profile_from_subscription(self.user.profile, self.subscription)
        self.assertEqual(int(self.user.profile.subscription_ends_at.timestamp()), 1850000000)
        self.assertEqual(int(self.user.profile.subscription_current_period_end.timestamp()), 1900000100)
        self.subscription.pop("cancel_at")
        self.subscription.pop("current_period_end")
        self.subscription["items"]["data"][0].pop("current_period_end")
        self.subscription["cancel_at_period_end"] = True
        update_profile_from_subscription(self.user.profile, self.subscription)
        response = self.client.get(self.billing)
        self.assertContains(response, "Your access end date is being confirmed")
        self.assertNotContains(response, "None")

    def test_refresh_failure_keeps_confirmed_state_and_is_sanitized(self):
        self.retrieve.side_effect = RuntimeError("private-provider-detail")
        response = self.client.get(self.billing + "?sync=1")
        self.assertContains(response, "Showing the last confirmed status")
        self.assertNotContains(response, "private-provider-detail")
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.plan, "premium")

    def test_pricing_copy_and_responsive_styles(self):
        response = self.client.get(self.billing)
        for text in ["$12.99 USD/month", "$24.99 USD/month", "Upgrade to Pro",
                     "prorated difference", "max-width: 640px", "focus-visible"]:
            self.assertContains(response, text)
        for text in ["unlimited bot creation", "You already have a subscription.",
                     "advanced features", "https://js.stripe.com/v3/"]:
            self.assertNotContains(response, text)

    def test_upgrade_accepts_real_stripe_sdk_objects(self):
        self.retrieve.side_effect = [stripe.Subscription.construct_from(value, "test")
                                     for value in [self.subscription, self.pro()]]
        self.post()
        self.modify.assert_called_once()
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.plan, "pro")

    def test_separate_browser_forms_do_not_upgrade_twice(self):
        other_token = self.client.get(self.billing).context["upgrade_token"]
        self.assertNotEqual(other_token, self.token)
        self.retrieve.side_effect = [self.subscription, self.pro(), self.pro()]
        self.post()
        self.post(upgrade_token=other_token)
        self.modify.assert_called_once()
        self.checkout.assert_not_called()

    def test_lost_upgrade_response_recovers_without_second_mutation(self):
        self.retrieve.side_effect = [self.subscription, self.pro()]
        self.modify.side_effect = stripe.error.APIConnectionError("private-provider-detail")
        self.post()
        # Stripe accepted the first request before the connection failed.
        other_token = self.client.get(self.billing).context["upgrade_token"]
        response = self.client.post(self.url, {"upgrade_token": other_token}, follow=True)
        self.assertContains(response, "already on Pro")
        self.modify.assert_called_once()
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.plan, "pro")

    def test_post_update_refresh_failure_can_recover_on_portal_return(self):
        self.retrieve.side_effect = [self.subscription, RuntimeError("private-provider-detail")]
        self.post()
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.plan, "premium")
        self.retrieve.side_effect = None
        self.retrieve.return_value = self.pro()
        self.client.get(self.billing + "?sync=1")
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.plan, "pro")
        self.modify.assert_called_once()

    def test_price_shape_and_stale_metadata_cannot_authorize_upgrade(self):
        variants = []
        for field, value in [("currency", "eur"), ("unit_amount", 2498),
                             ("billing_scheme", "tiered"),
                             ("transform_quantity", {"divide_by": 10, "round": "up"})]:
            sub = deepcopy(self.subscription)
            sub["items"]["data"][0]["price"][field] = value
            variants.append(sub)
        for field, value in [("interval", "year"), ("interval_count", 2),
                             ("usage_type", "metered")]:
            sub = deepcopy(self.subscription)
            sub["items"]["data"][0]["price"]["recurring"][field] = value
            variants.append(sub)
        sub = deepcopy(self.subscription)
        sub["items"]["data"][0]["quantity"] = 2
        variants.append(sub)
        sub = deepcopy(self.subscription)
        sub["items"]["data"] *= 2
        variants.append(sub)
        for sub in variants:
            with self.subTest(subscription=sub):
                self.retrieve.return_value = sub
                self.post()
                self.client.get(self.billing + "?sync=1")
                self.user.profile.refresh_from_db()
                self.assertEqual(self.user.profile.plan, "free")
        self.modify.assert_not_called()
        self.product.assert_not_called()

    def test_refresh_rejects_wrong_owner_without_changing_saved_state(self):
        before = type(self.user.profile).objects.values().get(pk=self.user.profile.pk)
        for field, value in [("customer", "cus_other"),
                             ("metadata", {"user_id": "999999"}), ("livemode", True)]:
            sub = self.pro()
            sub[field] = value
            self.retrieve.return_value = sub
            response = self.client.get(self.billing + "?sync=1&customer=cus_other")
            self.assertContains(response, "Showing the last confirmed status")
            self.assertEqual(type(self.user.profile).objects.values().get(pk=self.user.profile.pk), before)

    def test_billing_is_private_and_unsupported_methods_cannot_refresh(self):
        response = self.client.get(self.billing)
        self.assertIn("no-store", response["Cache-Control"])
        self.assertIn("private", response["Cache-Control"])
        for method in [self.client.post, self.client.put, self.client.delete]:
            self.assertEqual(method(self.billing + "?sync=1").status_code, 405)
        self.retrieve.assert_not_called()

    def test_past_due_scheduled_cancellation_does_not_promise_paid_access(self):
        self.subscription.update(status="past_due", cancel_at_period_end=True)
        response = self.client.get(self.billing + "?sync=1")
        self.assertContains(response, "Paid access is currently unavailable")
        self.assertNotContains(response, "Access through")
        self.assertNotContains(response, "Upgrade to Pro")
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.plan, "free")
        self.assertFalse(self.user.profile.is_subscribed)

    def test_missing_actual_cancellation_end_does_not_show_request_date(self):
        self.subscription.update(status="canceled", canceled_at=1800000000)
        response = self.client.get(self.billing + "?sync=1")
        self.assertContains(response, "The end date is not yet available")
        self.user.profile.refresh_from_db()
        self.assertIsNone(self.user.profile.subscription_ends_at)

    def test_all_nonterminal_subscription_states_block_checkout(self):
        for status in ["active", "trialing", "past_due", "unpaid", "incomplete", "paused", ""]:
            self.user.profile.stripe_subscription_status = status
            self.user.profile.save(update_fields=["stripe_subscription_status"])
            self.assertEqual(self.client.post(reverse("payments:create_checkout_session"),
                                              {"plan": "pro"}).status_code, 409)
        self.checkout.assert_not_called()
