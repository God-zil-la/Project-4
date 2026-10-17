from datetime import timedelta
from unittest.mock import Mock

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from .campaign import TOKEN_LIMIT, provider_call, redeem
from .models import UserProfile
from ai_assistant.bots.chat_service import ChatUsageLimitError


@override_settings(K1_CAMPAIGN_ENABLED=True, K1_CAMPAIGN_CODE="local-test-code")
class CampaignFinalRulesTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            username="k1-final-test-user",
            password="test-only-password",
        )
        self.profile, _ = UserProfile.objects.get_or_create(user=self.user)
        redeem(self.user, "local-test-code")
        self.profile.refresh_from_db()

    def test_two_million_tokens_block_provider_but_keep_pro(self):
        UserProfile.objects.filter(pk=self.profile.pk).update(
            campaign_tokens=TOKEN_LIMIT,
            campaign_reserved_tokens=0,
        )
        self.profile.refresh_from_db()

        self.assertTrue(self.profile.has_campaign_access)
        self.assertEqual(self.profile.effective_plan, UserProfile.PLAN_PRO)

        provider = Mock()

        with self.assertRaises(ChatUsageLimitError):
            provider_call(
                provider,
                campaign_user=self.user,
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=100,
            )

        provider.assert_not_called()

        self.profile.refresh_from_db()
        self.assertEqual(self.profile.campaign_tokens, TOKEN_LIMIT)
        self.assertEqual(self.profile.campaign_reserved_tokens, 0)

    def test_expired_campaign_restores_ordinary_premium(self):
        UserProfile.objects.filter(pk=self.profile.pk).update(
            plan=UserProfile.PLAN_PREMIUM,
            campaign_ends_at=timezone.now() - timedelta(seconds=1),
        )
        self.profile.refresh_from_db()

        self.assertFalse(self.profile.has_campaign_access)
        self.assertEqual(
            self.profile.effective_plan,
            UserProfile.PLAN_PREMIUM,
        )

    def test_expired_campaign_restores_ordinary_free(self):
        UserProfile.objects.filter(pk=self.profile.pk).update(
            campaign_ends_at=timezone.now() - timedelta(seconds=1),
        )
        self.profile.refresh_from_db()

        self.assertFalse(self.profile.has_campaign_access)
        self.assertEqual(
            self.profile.effective_plan,
            UserProfile.PLAN_FREE,
        )

    def test_campaign_end_date_is_exactly_fourteen_days(self):
        self.assertEqual(
            self.profile.campaign_ends_at - self.profile.campaign_started_at,
            timedelta(days=14),
        )
