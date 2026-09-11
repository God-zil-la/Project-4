"""An active contract with an unknown price must not force duplicate checkout."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import stripe
from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .webhooks import update_profile_from_subscription
from .models import SubscriptionRecovery


@override_settings(STRIPE_PUBLIC_KEY="pk_test_placeholder")
class LegacyRecoveryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="legacy-owner")
        self.client.force_login(self.user)
        self.billing = reverse("payments:billing")
        self.url = reverse("payments:recover_subscription")
        self.sub = {
            "id": "sub_legacy",
            "customer": "cus_owner",
            "livemode": False,
            "status": "active",
            "collection_method": "charge_automatically",
            "latest_invoice": {"id": "in_paid", "status": "paid"},
            "metadata": {"user_id": str(self.user.pk), "plan": "pro"},
            "items": {
                "data": [
                    {
                        "id": "si_legacy",
                        "quantity": 1,
                        "current_period_end": 1900000000,
                        "price": {
                            "id": "price_legacy",
                            "currency": "usd",
                            "unit_amount": 12900,
                            "recurring": {"interval": "month"},
                        },
                    }
                ]
            },
        }
        update_profile_from_subscription(self.user.profile, self.sub)

        self.inventory = [self.sub]

        self.listing = self.mock("Subscription.list")
        self.listing.side_effect = lambda **kw: SimpleNamespace(
            auto_paging_iter=lambda: iter(self.inventory)
        )

        self.retrieve = self.mock("Subscription.retrieve")
        self.retrieve.side_effect = lambda *args, **kw: self.sub

        self.modify = self.mock("Subscription.modify")

        self.product = self.mock("Product.create")
        self.product.return_value = SimpleNamespace(id="prod_current")

        self.checkout = self.mock("checkout.Session.create")
        self.create = self.mock("Subscription.create")
        self.cancel = self.mock("Subscription.cancel")

        self.sessions = self.mock("checkout.Session.list")
        self.sessions.return_value = SimpleNamespace(
            auto_paging_iter=lambda: iter([])
        )

        self.invoices = self.mock("Invoice.list")
        self.invoices.return_value = SimpleNamespace(
            auto_paging_iter=lambda: iter([])
        )

        self.pending = self.mock("InvoiceItem.list")
        self.pending.return_value = SimpleNamespace(
            auto_paging_iter=lambda: iter([])
        )

    def mock(self, name):
        patcher = patch("stripe." + name)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def token(self, plan="premium"):
        response = self.client.get(self.billing + "?sync=1")
        return next(
            option["token"]
            for option in response.context["recovery_options"]
            if option["plan"] == plan
        )

    def post(self, token):
        return self.client.post(
            self.url,
            {"recovery_token": token},
        )

    def test_active_unknown_usd_recovers_either_plan_on_same_subscription(self):
        original = deepcopy(self.sub)

        for plan, amount in [("premium", 2900), ("pro", 5900)]:
            with self.subTest(plan=plan):
                self.sub = deepcopy(original)
                self.inventory = [self.sub]

                update_profile_from_subscription(
                    self.user.profile,
                    self.sub,
                )

                self.assertEqual(self.user.profile.plan, "free")

                token = self.token(plan)

                def changed(*args, **kwargs):
                    self.sub["items"]["data"][0]["price"].update(
                        id="price_current",
                        unit_amount=amount,
                    )

                self.modify.side_effect = changed

                self.post(token)

                args, kwargs = self.modify.call_args

                self.assertEqual(args, ("sub_legacy",))
                self.assertEqual(
                    kwargs["items"][0]["id"],
                    "si_legacy",
                )
                self.assertEqual(
                    kwargs["items"][0]["price_data"]["unit_amount"],
                    amount,
                )
                self.assertEqual(
                    kwargs["payment_behavior"],
                    "error_if_incomplete",
                )
                self.assertNotIn(
                    "cancel_at_period_end",
                    kwargs,
                )

                self.user.profile.refresh_from_db()

                self.assertEqual(
                    self.user.profile.plan,
                    plan,
                )
                self.assertEqual(
                    self.user.profile.stripe_subscription_id,
                    "sub_legacy",
                )

                before = self.modify.call_count

                self.post(token)

                self.assertEqual(
                    self.modify.call_count,
                    before,
                )

        self.checkout.assert_not_called()
        self.create.assert_not_called()

    def test_uncertain_retry_and_new_tab_share_provider_key(self):
        first = self.token()

        self.modify.side_effect = stripe.error.APIConnectionError(
            "private-details"
        )

        self.post(first)

        key = self.modify.call_args.kwargs["idempotency_key"]

        self.post(self.token())

        self.assertEqual(
            self.modify.call_args.kwargs["idempotency_key"],
            key,
        )

        self.checkout.assert_not_called()

    def test_legacy_sek_offers_replacement_and_blocks_checkout(self):
        self.sub["items"]["data"][0]["price"]["currency"] = "sek"

        response = self.client.get(
            self.billing + "?sync=1"
        )
        content = response.content.decode()

        self.assertRegex(
            content,
            r"Replace legacy\s+test subscription with\s+Premium",
        )
        self.assertRegex(
            content,
            r"Replace legacy\s+test subscription with\s+Pro",
        )

        self.assertTrue(
            response.context["recovery_options"]
        )

        self.user.profile.refresh_from_db()

        self.assertEqual(
            self.user.profile.plan,
            "free",
        )
        self.assertEqual(
            self.user.profile.stripe_subscription_status,
            "active",
        )

        for plan in ("premium", "pro"):
            response = self.client.post(
                reverse("payments:create_checkout_session"),
                {"plan": plan},
            )
            self.assertEqual(
                response.status_code,
                409,
            )

        self.checkout.assert_not_called()

    def test_owner_mode_state_and_stale_item_are_rechecked_on_post(self):
        token = self.token()
        original = deepcopy(self.sub)

        for key, value in [
            ("customer", "cus_other"),
            ("livemode", True),
            ("metadata", {"user_id": "99999"}),
            ("status", "past_due"),
            ("latest_invoice", {"status": "open"}),
            ("schedule", "sched_other"),
            ("pending_update", {"expires_at": 1900000000}),
            ("pause_collection", {"behavior": "void"}),
            ("cancel_at", 1),
        ]:
            self.sub = deepcopy(original)
            self.sub[key] = value
            self.inventory = [self.sub]
            self.post(token)

        self.sub = deepcopy(original)
        self.sub["items"]["data"][0]["id"] = "si_replaced"
        self.inventory = [self.sub]
        self.post(token)

        self.inventory = [
            original,
            dict(original, id="sub_second"),
        ]
        self.post(token)

        self.modify.assert_not_called()
        self.product.assert_not_called()

    def test_login_csrf_signed_target_and_method_required(self):
        token = self.token()

        self.assertEqual(
            Client().post(self.url).status_code,
            302,
        )

        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)

        self.assertEqual(
            csrf.post(
                self.url,
                {"recovery_token": token},
            ).status_code,
            403,
        )

        self.assertEqual(
            self.client.get(self.url).status_code,
            405,
        )

        self.post("invalid")

        other = User.objects.create_user(
            username="other-owner"
        )
        self.client.force_login(other)
        self.post(token)

        self.modify.assert_not_called()

    def test_payment_failure_never_grants_access_or_creates_checkout(self):
        self.modify.side_effect = stripe.error.CardError(
            "private-details",
            "card",
            "card_declined",
        )

        response = self.client.post(
            self.url,
            {"recovery_token": self.token()},
            follow=True,
        )

        self.assertContains(
            response,
            "Payment could not be completed",
        )
        self.assertNotContains(
            response,
            "private-details",
        )

        self.user.profile.refresh_from_db()

        self.assertEqual(
            self.user.profile.plan,
            "free",
        )

        self.checkout.assert_not_called()
        self.create.assert_not_called()

    def prepare_sek(self):
        self.sub["items"]["data"][0]["price"]["currency"] = "sek"
        self.sub["cancel_at_period_end"] = True

        def cancel(*args, **kwargs):
            self.assertTrue(
                SubscriptionRecovery.objects.exists()
            )
            self.sub["status"] = "canceled"

        self.cancel.side_effect = cancel

        def create(**kwargs):
            self.assertEqual(
                self.sub["status"],
                "canceled",
            )

            result = deepcopy(self.sub)
            result.update(
                id="sub_replacement",
                status="active",
                metadata=kwargs["metadata"],
                cancel_at=kwargs.get("cancel_at"),
                cancel_at_period_end=False,
            )

            result["items"]["data"][0]["price"].update(
                kwargs["items"][0]["price_data"]
            )

            self.inventory.append(result)

            return result

        self.create.side_effect = create

    def test_sek_replacement_has_no_overlap_and_preserves_cancellation_for_both_plans(
        self,
    ):
        original = deepcopy(self.sub)

        for plan in ("premium", "pro"):
            with self.subTest(plan=plan):
                SubscriptionRecovery.objects.all().delete()

                self.sub = deepcopy(original)
                self.inventory = [self.sub]

                update_profile_from_subscription(
                    self.user.profile,
                    self.sub,
                )

                self.prepare_sek()

                token = self.token(plan)
                self.post(token)

                self.user.profile.refresh_from_db()

                self.assertEqual(
                    self.user.profile.plan,
                    plan,
                )
                self.assertEqual(
                    self.user.profile.stripe_subscription_id,
                    "sub_replacement",
                )
                self.assertEqual(
                    int(
                        self.user.profile.subscription_ends_at.timestamp()
                    ),
                    1900000000,
                )

                self.assertTrue(
                    SubscriptionRecovery.objects.get().completed
                )

                kwargs = self.create.call_args.kwargs

                self.assertEqual(
                    kwargs["payment_behavior"],
                    "error_if_incomplete",
                )
                self.assertEqual(
                    kwargs["proration_behavior"],
                    "none",
                )

                before = self.create.call_count

                self.post(token)

                self.assertEqual(
                    self.create.call_count,
                    before,
                )

        self.modify.assert_not_called()
        self.checkout.assert_not_called()

    def test_sek_unknown_create_result_recovers_inventory_without_second_create(
        self,
    ):
        self.prepare_sek()

        create = self.create.side_effect

        def uncertain(**kwargs):
            create(**kwargs)
            raise stripe.error.APIConnectionError(
                "private-details"
            )

        self.create.side_effect = uncertain

        token = self.token()

        self.post(token)

        self.assertFalse(
            SubscriptionRecovery.objects.get().completed
        )

        self.post(token)

        self.assertTrue(
            SubscriptionRecovery.objects.get().completed
        )

        self.create.assert_called_once()
        self.cancel.assert_called_once()

        self.user.profile.refresh_from_db()

        self.assertEqual(
            self.user.profile.plan,
            "premium",
        )

    def test_sek_payment_failure_keeps_durable_guard_and_same_retry_request(
        self,
    ):
        self.prepare_sek()

        self.create.side_effect = stripe.error.CardError(
            "private-details",
            "card",
            "card_declined",
        )

        token = self.token()

        self.post(token)

        first = deepcopy(
            self.create.call_args.kwargs
        )

        self.post(token)

        self.assertEqual(
            self.create.call_args.kwargs,
            first,
        )

        self.assertFalse(
            SubscriptionRecovery.objects.get().completed
        )

        self.assertEqual(
            self.client.post(
                reverse(
                    "payments:create_checkout_session"
                ),
                {"plan": "pro"},
            ).status_code,
            409,
        )

        self.checkout.assert_not_called()
        self.cancel.assert_called_once()

    def test_sek_cancellation_uncertain_is_retrieved_before_create(self):
        self.prepare_sek()

        def uncertain(*args, **kwargs):
            self.sub["status"] = "canceled"
            raise stripe.error.APIConnectionError(
                "private-details"
            )

        self.cancel.side_effect = uncertain

        token = self.token()

        self.post(token)
        self.create.assert_not_called()

        self.post(token)
        self.create.assert_called_once()

    def test_sek_outstanding_invoice_or_open_checkout_prevents_cancellation(
        self,
    ):
        self.prepare_sek()

        token = self.token()

        self.invoices.return_value = SimpleNamespace(
            auto_paging_iter=lambda: iter(
                [{"status": "open"}]
            )
        )

        self.post(token)

        self.cancel.assert_not_called()
        self.create.assert_not_called()

    def test_sek_expired_uncertain_intent_requires_support(self):
        from datetime import timedelta

        from django.utils import timezone

        self.prepare_sek()

        self.create.side_effect = (
            stripe.error.APIConnectionError(
                "private-details"
            )
        )

        token = self.token()

        self.post(token)

        SubscriptionRecovery.objects.update(
            started_at=(
                timezone.now()
                - timedelta(hours=24)
            )
        )

        self.post(token)

        self.create.assert_called_once()

        self.assertFalse(
            SubscriptionRecovery.objects.get().completed
        )

    def test_replacement_webhook_before_response_keeps_email_processing(
        self,
    ):
        import json

        self.prepare_sek()

        create = self.create.side_effect

        def uncertain(**kwargs):
            create(**kwargs)
            raise stripe.error.APIConnectionError(
                "private-details"
            )

        self.create.side_effect = uncertain

        self.post(self.token())

        replacement = self.inventory[-1]

        self.retrieve.side_effect = (
            lambda sid, **kw:
            self.sub
            if sid == self.sub["id"]
            else replacement
        )

        event = {
            "id": "evt_recovery",
            "livemode": False,
            "type": "customer.subscription.created",
            "data": {
                "object": replacement
            },
        }

        with patch(
            "stripe.Webhook.construct_event"
        ), patch(
            "ai_assistant.payments.webhooks.queue_subscription_emails"
        ) as emails:
            response = self.client.post(
                reverse("payments:webhook"),
                json.dumps(event),
                content_type="application/json",
            )

            self.assertEqual(
                response.status_code,
                200,
            )

            emails.assert_called_once()

        self.user.profile.refresh_from_db()

        self.assertEqual(
            self.user.profile.stripe_subscription_id,
            "sub_replacement",
        )
        self.assertEqual(
            self.user.profile.plan,
            "premium",
        )

    def test_sek_different_tab_target_cannot_replace_saved_intent(self):
        self.prepare_sek()

        premium = self.token("premium")
        pro = self.token("pro")

        self.create.side_effect = (
            stripe.error.APIConnectionError(
                "private-details"
            )
        )

        self.post(premium)
        self.post(pro)

        self.create.assert_called_once()

        self.assertEqual(
            SubscriptionRecovery.objects.get().plan,
            "premium",
        )

    def test_sek_unconfirmed_cancel_never_creates_replacement(self):
        self.prepare_sek()

        self.cancel.side_effect = None

        self.post(self.token())

        self.create.assert_not_called()

        self.assertFalse(
            SubscriptionRecovery.objects.get().completed
        )

    def test_sek_open_checkout_never_cancels(self):
        self.prepare_sek()

        self.sessions.return_value = SimpleNamespace(
            auto_paging_iter=lambda: iter(
                [
                    {
                        "mode": "subscription",
                        "status": "open",
                    }
                ]
            )
        )

        self.post(self.token())

        self.cancel.assert_not_called()
        self.create.assert_not_called()