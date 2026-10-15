"""Offline tests for Premium Discord installation verification."""
from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase
from .premium_discord_discord_api import (
    DiscordOAuthError, authorization_url, authorized_manageable_guilds, verify_bot_membership,
)


class PremiumDiscordInstallationTests(SimpleTestCase):
    @patch.dict("os.environ", {
        "PREMIUM_DISCORD_CLIENT_ID": "123",
        "PREMIUM_DISCORD_CLIENT_SECRET": "not-a-real-secret",
        "PREMIUM_DISCORD_REDIRECT_URI": "https://example.org/bots/api/premium-discord/callback/",
    })
    def test_install_url_requests_bot_and_guild_permissions(self):
        url = authorization_url("signed-state")
        self.assertIn("bot", url)
        self.assertIn("applications.commands", url)
        self.assertIn("identify", url)

    @patch("ai_assistant.bots.premium_discord_discord_api._discord_json")
    def test_only_manageable_guilds_are_allowed(self, fetch):
        fetch.return_value = [
            {"id": "123", "name": "Allowed", "permissions": "32", "owner": False},
            {"id": "456", "name": "Denied", "permissions": "0", "owner": False},
            {"id": "789", "name": "Owner", "permissions": "0", "owner": True},
        ]
        self.assertEqual(
            authorized_manageable_guilds("fake-token"),
            {"123": "Allowed", "789": "Owner"},
        )

    @patch.dict("os.environ", {"PREMIUM_DISCORD_BOT_TOKEN": "fake-token"})
    @patch("ai_assistant.bots.premium_discord_discord_api.urllib.request.urlopen")
    def test_installed_bot_is_verified_by_discord(self, urlopen):
        response = MagicMock()
        response.read.return_value = b'{"id":"123"}'
        urlopen.return_value.__enter__.return_value = response
        self.assertTrue(verify_bot_membership("123"))

    @patch.dict("os.environ", {"PREMIUM_DISCORD_BOT_TOKEN": ""})
    def test_missing_bot_token_fails_closed(self):
        with self.assertRaises(DiscordOAuthError):
            verify_bot_membership("123")
