"""Offline tests for U6.3 Free Live Voice entitlement."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from ai_assistant.accounts.models import UserProfile
from .live_free_entitlement import (
    FreeVoiceAccessDenied,
    require_free_voice_access,
)


class FreeVoiceEntitlementTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="u63_free_entitlement_test",
            password="local-test-only-password",
        )
        self.profile, _ = UserProfile.objects.get_or_create(
            user=self.user
        )

    def check_denied(self):
        with self.assertRaises(FreeVoiceAccessDenied):
            require_free_voice_access(user=self.user)

    def test_ordinary_free_account(self):
        self.assertEqual(
            require_free_voice_access(user=self.user).pk,
            self.profile.pk,
        )

    def test_inactive_account_denied(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.check_denied()

    def test_premium_denied(self):
        self.profile.plan = UserProfile.PLAN_PREMIUM
        self.profile.save(update_fields=["plan"])
        self.check_denied()

    def test_pro_denied(self):
        self.profile.plan = UserProfile.PLAN_PRO
        self.profile.save(update_fields=["plan"])
        self.check_denied()

    def test_active_k1_campaign_denied(self):
        now = timezone.now()
        self.profile.campaign_started_at = now - timedelta(hours=1)
        self.profile.campaign_ends_at = now + timedelta(days=13)
        self.profile.save(
            update_fields=["campaign_started_at", "campaign_ends_at"]
        )
        self.check_denied()

    def test_complimentary_pro_denied(self):
        self.profile.complimentary_plan = UserProfile.PLAN_PRO
        self.profile.save(update_fields=["complimentary_plan"])
        self.check_denied()

    def test_subscription_flag_denied(self):
        self.profile.is_subscribed = True
        self.profile.save(update_fields=["is_subscribed"])
        self.check_denied()

    def test_stripe_customer_denied(self):
        self.profile.stripe_customer_id = "cus_test_local"
        self.profile.save(update_fields=["stripe_customer_id"])
        self.check_denied()

    def test_stripe_subscription_denied(self):
        self.profile.stripe_subscription_id = "sub_test_local"
        self.profile.save(update_fields=["stripe_subscription_id"])
        self.check_denied()

    def test_stripe_status_denied(self):
        self.profile.stripe_subscription_status = "active"
        self.profile.save(update_fields=["stripe_subscription_status"])
        self.check_denied()

    def test_unauthenticated_denied(self):
        from django.contrib.auth.models import AnonymousUser

        with self.assertRaises(FreeVoiceAccessDenied):
            require_free_voice_access(user=AnonymousUser())
