"""Focused Discord authentication tests; providers are never called."""
import hashlib
import io
import zipfile
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIClient

from .discord_auth import issue_discord_integration
from .models import Bot, DiscordIntegration


class DiscordAuthenticationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="discord-owner", password="test-only-pass")
        self.other = User.objects.create_user(username="discord-other")
        self.owner.profile.plan = "pro"
        self.owner.profile.save(update_fields=["plan"])
        self.bot = Bot.objects.create(owner=self.owner, name="Discord assistant")
        self.other_bot = Bot.objects.create(owner=self.other, name="Other assistant")
        self.integration, self.secret = issue_discord_integration(self.owner, self.bot)
        self.token = Token.objects.create(user=self.owner)
        self.client_api = APIClient()
        self.discord_url = reverse("bots:discord-api-bot-chat", args=[self.bot.pk])
        self.normal_url = reverse("bots:api-bot-chat", args=[self.bot.pk])
        self.ai_patch = patch("ai_assistant.bots.api_views.process_bot_message", return_value={"response": "ok"})
        self.ai = self.ai_patch.start()
        self.addCleanup(self.ai_patch.stop)

    def chat(self, credential=None, url=None):
        self.ai.reset_mock()
        return self.client_api.post(
            url or self.discord_url, {"message": "Hello", "require_pro": False},
            format="json", HTTP_AUTHORIZATION=credential or "Discord " + self.secret,
        )

    def test_valid_and_invalid_discord_credentials(self):
        self.assertEqual(self.chat().status_code, 200)
        self.ai.assert_called_once()
        self.assertEqual(self.ai.call_args.kwargs["user"], self.owner)
        self.assertEqual(self.ai.call_args.kwargs["bot"], self.bot)
        for value in ("Discord dsc_" + "0" * 64, "Discord invalid", "Discord", "Bearer " + self.secret):
            with self.subTest(value=value.split()[0]):
                self.assertEqual(self.chat(value).status_code, 401)
                self.ai.assert_not_called()

    def test_pro_is_checked_on_each_request_before_ai(self):
        self.assertEqual(self.chat().status_code, 200)
        for plan in ("premium", "free"):
            self.owner.profile.plan = plan
            self.owner.profile.save(update_fields=["plan"])
            self.assertEqual(self.chat().status_code, 403)
            self.ai.assert_not_called()
        self.owner.profile.refresh_from_db()
        self.assertEqual(self.owner.profile.monthly_message_count, 0)

    def test_bot_binding_and_owner_isolation(self):
        own_second = Bot.objects.create(owner=self.owner, name="Another owned assistant")
        for bot in (own_second, self.other_bot):
            self.assertEqual(self.chat(url=reverse("bots:discord-api-bot-chat", args=[bot.pk])).status_code, 401)
            self.ai.assert_not_called()
        self.bot.owner = self.other
        self.bot.save(update_fields=["owner"])
        self.assertEqual(self.chat().status_code, 401)
        self.ai.assert_not_called()

    def test_inactive_user_and_missing_profile(self):
        self.owner.is_active = False
        self.owner.save(update_fields=["is_active"])
        self.assertEqual(self.chat().status_code, 401)
        self.ai.assert_not_called()
        self.owner.is_active = True
        self.owner.save(update_fields=["is_active"])
        self.owner.profile.delete()
        self.assertEqual(self.chat().status_code, 403)
        self.ai.assert_not_called()

    def test_normal_token_and_session_rejected_on_discord(self):
        self.assertEqual(self.chat("Token " + self.token.key).status_code, 401)
        self.ai.assert_not_called()
        self.client_api.force_login(self.owner)
        self.assertEqual(self.client_api.post(self.discord_url, {"message": "Hello"}).status_code, 401)
        self.ai.assert_not_called()

    def test_discord_secret_rejected_on_normal_api(self):
        for scheme in ("Discord", "Token"):
            self.assertEqual(self.chat(scheme + " " + self.secret, self.normal_url).status_code, 401)
            self.ai.assert_not_called()

    def test_normal_token_and_session_chat_do_not_require_pro(self):
        self.owner.profile.plan = "free"
        self.owner.profile.save(update_fields=["plan"])
        self.assertEqual(self.chat("Token " + self.token.key, self.normal_url).status_code, 200)
        self.ai.assert_called_once()
        self.client_api.force_login(self.owner)
        self.ai.reset_mock()
        self.assertEqual(self.client_api.post(self.normal_url, {"message": "Hello"}).status_code, 200)
        self.ai.assert_called_once()

    def test_revocation_requires_owner_post_and_csrf_even_without_pro(self):
        web = Client(enforce_csrf_checks=True)
        url = reverse("bots:discord-revoke", args=[self.bot.pk, self.integration.pk])
        web.force_login(self.owner)
        self.assertEqual(web.get(url).status_code, 405)
        self.assertEqual(web.post(url).status_code, 403)
        self.owner.profile.plan = "free"
        self.owner.profile.save(update_fields=["plan"])
        self.assertEqual(web.get(reverse("bots:discord-setup", args=[self.bot.pk])).status_code, 200)
        csrf = web.cookies["csrftoken"].value
        self.assertEqual(web.post(url, HTTP_X_CSRFTOKEN=csrf).status_code, 302)
        self.integration.refresh_from_db()
        self.assertIsNotNone(self.integration.revoked_at)
        self.assertEqual(self.chat().status_code, 401)
        self.ai.assert_not_called()
        self.assertTrue(Token.objects.filter(pk=self.token.pk).exists())
        self.assertEqual(self.chat("Token " + self.token.key, self.normal_url).status_code, 200)
        web.force_login(self.other)
        web.get(reverse("bots:discord-setup", args=[self.other_bot.pk]))
        self.assertEqual(web.post(url, HTTP_X_CSRFTOKEN=web.cookies["csrftoken"].value).status_code, 404)

    def test_hash_storage_and_independent_credentials(self):
        second, secret = issue_discord_integration(self.owner, self.bot)
        self.assertNotEqual(secret, self.secret)
        self.integration.refresh_from_db()
        self.assertEqual(self.integration.secret_hash, hashlib.sha256(self.secret.encode("ascii")).hexdigest())
        self.assertNotIn(self.secret, str(DiscordIntegration.objects.values().get(pk=self.integration.pk)))
        self.assertNotEqual(second.secret_hash, self.integration.secret_hash)
        with self.assertRaises(AuthenticationFailed):
            issue_discord_integration(self.other, self.bot)

    def test_download_is_in_memory_no_store_and_contains_only_integration_credential(self):
        from django.http import FileResponse

        def checked_file_response(buffer, *args, **kwargs):
            self.assertIsInstance(buffer, io.BytesIO)
            return FileResponse(buffer, *args, **kwargs)

        self.client.force_login(self.owner)
        with patch("ai_assistant.bots.discord_download.FileResponse", side_effect=checked_file_response) as response_factory:
            response = self.client.post(reverse("bots:discord-download", args=[self.bot.pk]), {"discord_token": "test.discord-token"})
        response_factory.assert_called_once()
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response, FileResponse)
        self.assertIn("no-store", response["Cache-Control"])
        data = b"".join(response.streaming_content)
        response.close()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            env = archive.read("discord_bridge/.env").decode("utf-8")
            credential = next(line.split("=", 1)[1] for line in env.splitlines() if line.startswith("DJANGO_API_TOKEN="))
        self.assertNotIn(self.token.key, env)
        self.assertTrue(DiscordIntegration.objects.filter(secret_hash=hashlib.sha256(credential.encode("ascii")).hexdigest()).exists())
        self.assertEqual(self.chat("Discord " + credential).status_code, 200)

    def test_download_rejects_dotenv_injection_and_rolls_back_failed_archive(self):
        self.client.force_login(self.owner)
        url = reverse("bots:discord-download", args=[self.bot.pk])
        before = DiscordIntegration.objects.count()
        self.assertEqual(self.client.post(url, {"discord_token": "token\nINJECT=value"}).status_code, 400)
        self.assertEqual(DiscordIntegration.objects.count(), before)
        with patch("ai_assistant.bots.discord_download.zipfile.ZipFile.write", side_effect=OSError("test failure")):
            with self.assertRaises(OSError):
                self.client.post(url, {"discord_token": "test-token"})
        self.assertEqual(DiscordIntegration.objects.count(), before)
