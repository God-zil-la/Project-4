"""Premium Discord persistence tests; no live Discord or Pro U5 calls."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_assistant.accounts.models import UserProfile
from .premium_discord_guild_service import (
    connect_verified_guild, disconnect_guild, resolve_active_premium_guild,
)
from .premium_discord_models import PremiumDiscordGuild
from .premium_discord_policy import PremiumDiscordPolicyError


class PremiumDiscordGuildServiceTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="premium_guild_owner", password="unused")
        self.profile, _ = UserProfile.objects.get_or_create(user=self.owner)
        self.profile.plan = UserProfile.PLAN_PREMIUM
        self.profile.save()

    def connect(self, guild_id):
        return connect_verified_guild(
            owner=self.owner, guild_id=str(guild_id),
            guild_name="Test guild", authorization_verified=True,
        )

    def test_requires_verified_authorization(self):
        with self.assertRaises(PremiumDiscordPolicyError):
            connect_verified_guild(owner=self.owner, guild_id="123")
        self.assertEqual(PremiumDiscordGuild.objects.count(), 0)

    def test_three_servers_and_reconnect(self):
        for guild_id in (1001, 1002, 1003):
            self.connect(guild_id)
        with self.assertRaises(PremiumDiscordPolicyError):
            self.connect(1004)
        self.connect(1002)
        self.assertEqual(PremiumDiscordGuild.objects.filter(disconnected_at__isnull=True).count(), 3)
        self.assertTrue(disconnect_guild(owner=self.owner, guild_id="1002"))
        self.connect(1004)
        self.assertEqual(PremiumDiscordGuild.objects.filter(disconnected_at__isnull=True).count(), 3)

    def test_unlink_blocks_access(self):
        self.connect(1001)
        self.assertIsNotNone(resolve_active_premium_guild("1001"))
        self.assertTrue(disconnect_guild(owner=self.owner, guild_id="1001"))
        self.assertIsNone(resolve_active_premium_guild("1001"))
        self.assertFalse(disconnect_guild(owner=self.owner, guild_id="1001"))

    def test_other_account_cannot_take_guild(self):
        self.connect(1001)
        other = get_user_model().objects.create_user(username="other_premium_guild_owner")
        profile, _ = UserProfile.objects.get_or_create(user=other)
        profile.plan = UserProfile.PLAN_PREMIUM
        profile.save()
        with self.assertRaises(PremiumDiscordPolicyError):
            connect_verified_guild(owner=other, guild_id="1001", authorization_verified=True)
