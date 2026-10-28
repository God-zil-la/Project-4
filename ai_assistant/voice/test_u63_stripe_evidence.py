from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from ai_assistant.accounts.models import UserProfile
from ai_assistant.voice.service import VoiceAccessDenied
from ai_assistant.voice.stripe_evidence import resolve_stripe_voice_evidence
from ai_assistant.stt.normalizer import normalize


@override_settings(STRIPE_SECRET_KEY="sk_test_u63_mock_only")
class StripeVoiceEvidenceTests(TestCase):

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="u63_stripe_test",
            password="test-password",
        )
        self.profile = UserProfile.objects.get(user=self.user)
        self.profile.stripe_customer_id = "cus_test_u63"
        self.profile.stripe_subscription_id = "sub_test_u63"
        self.profile.save()

        now = datetime.now(timezone.utc)
        self.start = int((now - timedelta(days=2)).timestamp())
        self.end = int((now + timedelta(days=28)).timestamp())

    def subscription(self):
        return {
            "id": "sub_test_u63",
            "customer": "cus_test_u63",
            "livemode": False,
            "metadata": {"user_id": str(self.user.pk)},
            "status": "active",
            "current_period_start": self.start,
            "current_period_end": self.end,
            "items": {
                "data": [{
                    "id": "si_test_u63",
                    "quantity": 1,
                    "price": {
                        "currency": "usd",
                        "unit_amount": 2999,
                        "recurring": {
                            "interval": "month",
                            "interval_count": 1,
                        },
                    },
                }],
            },
        }

    @patch(
        "ai_assistant.voice.stripe_evidence.get_plan_from_subscription",
        return_value=UserProfile.PLAN_PREMIUM,
    )
    @patch("ai_assistant.voice.stripe_evidence.validate_subscription")
    @patch("ai_assistant.voice.stripe_evidence.stripe.Subscription.retrieve")
    def test_valid_subscription(
        self, retrieve, validate, plan
    ):
        retrieve.return_value = self.subscription()

        evidence = resolve_stripe_voice_evidence(user=self.user)
        period = normalize(evidence)

        self.assertEqual(period.user_id, self.user.pk)
        self.assertEqual(period.plan, "premium")
        validate.assert_called_once()

    @patch(
        "ai_assistant.voice.stripe_evidence.get_plan_from_subscription",
        return_value=UserProfile.PLAN_PREMIUM,
    )
    @patch("ai_assistant.voice.stripe_evidence.validate_subscription")
    @patch("ai_assistant.voice.stripe_evidence.stripe.Subscription.retrieve")
    def test_expired_subscription_rejected(
        self, retrieve, validate, plan
    ):
        data = self.subscription()
        data["current_period_end"] = self.start
        retrieve.return_value = data

        with self.assertRaises(VoiceAccessDenied):
            resolve_stripe_voice_evidence(user=self.user)

    @patch(
        "ai_assistant.voice.stripe_evidence.get_plan_from_subscription",
        return_value=UserProfile.PLAN_PREMIUM,
    )
    @patch("ai_assistant.voice.stripe_evidence.validate_subscription")
    @patch("ai_assistant.voice.stripe_evidence.stripe.Subscription.retrieve")
    def test_wrong_owner_rejected(
        self, retrieve, validate, plan
    ):
        data = self.subscription()
        data["id"] = "sub_other_owner"
        retrieve.return_value = data

        with self.assertRaises(VoiceAccessDenied):
            resolve_stripe_voice_evidence(user=self.user)

    @patch("ai_assistant.voice.stripe_evidence.stripe.Subscription.retrieve")
    def test_stripe_failure_rejected(self, retrieve):
        retrieve.side_effect = RuntimeError("Stripe unavailable")

        with self.assertRaises(VoiceAccessDenied):
            resolve_stripe_voice_evidence(user=self.user)


    @patch(
        "ai_assistant.voice.stripe_evidence.get_plan_from_subscription",
        return_value=UserProfile.PLAN_PREMIUM,
    )
    @patch("ai_assistant.voice.stripe_evidence.validate_subscription")
    @patch("ai_assistant.voice.stripe_evidence.stripe.Subscription.retrieve")
    def test_conflicting_period_rejected(self, retrieve, validate, plan):
        data = self.subscription()
        data["items"]["data"][0]["current_period_end"] = self.end + 3600
        retrieve.return_value = data

        with self.assertRaises(VoiceAccessDenied):
            resolve_stripe_voice_evidence(user=self.user)

    @patch(
        "ai_assistant.voice.stripe_evidence.get_plan_from_subscription",
        return_value=UserProfile.PLAN_PREMIUM,
    )
    @patch("ai_assistant.voice.stripe_evidence.validate_subscription")
    @patch("ai_assistant.voice.stripe_evidence.stripe.Subscription.retrieve")
    def test_missing_item_identity_rejected(self, retrieve, validate, plan):
        data = self.subscription()
        data["items"]["data"][0].pop("id")
        retrieve.return_value = data

        with self.assertRaises(VoiceAccessDenied):
            resolve_stripe_voice_evidence(user=self.user)

    @patch("ai_assistant.voice.stripe_evidence.stripe.Subscription.retrieve")
    def test_real_validation_rejects_wrong_customer(self, retrieve):
        data = self.subscription()
        data["customer"] = "cus_wrong_owner"
        retrieve.return_value = data

        with self.assertRaises(VoiceAccessDenied):
            resolve_stripe_voice_evidence(user=self.user)

    @patch("ai_assistant.voice.stripe_evidence.stripe.Subscription.retrieve")
    def test_real_validation_rejects_wrong_metadata_owner(self, retrieve):
        data = self.subscription()
        data["metadata"]["user_id"] = "99999999"
        retrieve.return_value = data

        with self.assertRaises(VoiceAccessDenied):
            resolve_stripe_voice_evidence(user=self.user)

    @patch("ai_assistant.voice.stripe_evidence.stripe.Subscription.retrieve")
    def test_real_plan_validation_rejects_non_monthly(self, retrieve):
        data = self.subscription()
        data["items"]["data"][0]["price"]["recurring"]["interval"] = "year"
        retrieve.return_value = data

        with self.assertRaises(VoiceAccessDenied):
            resolve_stripe_voice_evidence(user=self.user)

    @patch("ai_assistant.voice.stripe_evidence.stripe.Subscription.retrieve")
    def test_real_validation_rejects_wrong_environment(self, retrieve):
        data = self.subscription()
        data["livemode"] = True
        retrieve.return_value = data

        with self.assertRaises(VoiceAccessDenied):
            resolve_stripe_voice_evidence(user=self.user)
