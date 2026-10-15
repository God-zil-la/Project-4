"""Pure Premium Discord policy tests; no network, billing or U5 mutations."""
from types import SimpleNamespace
from django.test import SimpleTestCase

from .premium_discord_policy import (
    MAX_PREMIUM_DISCORD_GUILDS,
    PremiumDiscordPolicyError,
    check_premium_discord_capacity,
    is_premium_discord_eligible,
)


def profile(plan="premium", active=True):
    return SimpleNamespace(effective_plan=plan, user=SimpleNamespace(is_active=active))


class PremiumDiscordPolicyTests(SimpleTestCase):
    def test_premium_only_and_active_account(self):
        self.assertTrue(is_premium_discord_eligible(profile()))
        for plan in ("free", "pro", "business", None):
            self.assertFalse(is_premium_discord_eligible(profile(plan)))
        self.assertFalse(is_premium_discord_eligible(profile(active=False)))
        self.assertFalse(is_premium_discord_eligible(None))

    def test_three_server_limit(self):
        self.assertEqual(MAX_PREMIUM_DISCORD_GUILDS, 3)
        self.assertEqual(check_premium_discord_capacity(profile(), [], "123").available_slots, 2)
        self.assertEqual(check_premium_discord_capacity(profile(), ["1", "2"], "3").available_slots, 0)
        with self.assertRaises(PremiumDiscordPolicyError):
            check_premium_discord_capacity(profile(), ["1", "2", "3"], "4")

    def test_existing_server_does_not_use_another_slot(self):
        result = check_premium_discord_capacity(profile(), ["1", "2", "3"], "2")
        self.assertEqual(result.active_guilds, 3)
        self.assertEqual(result.available_slots, 0)

    def test_rejects_invalid_ids_and_ineligible_plans(self):
        for invalid in ("", "0", "-1", "not-a-guild", True):
            with self.assertRaises(PremiumDiscordPolicyError):
                check_premium_discord_capacity(profile(), [], invalid)
        for plan in ("free", "pro"):
            with self.assertRaises(PremiumDiscordPolicyError):
                check_premium_discord_capacity(profile(plan), [], "123")
