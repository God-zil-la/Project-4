from datetime import timedelta
from unittest.mock import patch

from django.test import SimpleTestCase
from django.utils import timezone

from .models import UserProfile


class CampaignEntitlementRegressionTests(SimpleTestCase):
    def make_profile(self, tokens=0, start_offset=-1, end_offset=13):
        now = timezone.now()
        return UserProfile(
            plan=UserProfile.PLAN_FREE,
            campaign_started_at=now + timedelta(days=start_offset),
            campaign_ends_at=now + timedelta(days=end_offset),
            campaign_tokens=tokens,
        )

    def test_pro_access_remains_after_token_cap(self):
        profile = self.make_profile(tokens=2_000_000)
        self.assertTrue(profile.has_campaign_access)

        with patch(
            "ai_assistant.payments.store_service.store_plan",
            return_value=UserProfile.PLAN_FREE,
        ):
            self.assertEqual(profile.effective_plan, UserProfile.PLAN_PRO)

    def test_pro_access_expires_after_fourteen_days(self):
        profile = self.make_profile(
            tokens=0,
            start_offset=-15,
            end_offset=-1,
        )
        self.assertFalse(profile.has_campaign_access)

        with patch(
            "ai_assistant.payments.store_service.store_plan",
            return_value=UserProfile.PLAN_FREE,
        ):
            self.assertEqual(profile.effective_plan, UserProfile.PLAN_FREE)

    def test_future_campaign_does_not_grant_pro(self):
        profile = self.make_profile(
            start_offset=1,
            end_offset=15,
        )
        self.assertFalse(profile.has_campaign_access)

    def test_token_allowance_does_not_control_pro_entitlement(self):
        for tokens in (0, 1_999_999, 2_000_000):
            with self.subTest(tokens=tokens):
                profile = self.make_profile(tokens=tokens)
                self.assertTrue(profile.has_campaign_access)
