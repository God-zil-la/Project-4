import base64
import io
import zipfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from ai_assistant.accounts.models import UserProfile
from ai_assistant.bots.models import Bot, DiscordIntegration


class NativeU5MobileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.owner = User.objects.create_user(
            username="native_u5_owner",
            email="native_u5_owner@example.com",
            password="TestPassword123!"
        )
        cls.other = User.objects.create_user(
            username="native_u5_other",
            email="native_u5_other@example.com",
            password="TestPassword123!"
        )

    def setUp(self):
        self.client = APIClient()
        self.owner_token, _ = Token.objects.get_or_create(user=self.owner)
        self.other_token, _ = Token.objects.get_or_create(user=self.other)

    def authenticate(self, token):
        self.client.credentials(HTTP_AUTHORIZATION="Token " + token.key)

    def api_url(self):
        return reverse("accounts:native-u5-api-access")

    def discord_url(self, bot_id):
        return reverse("bots:native-u5-discord", args=[bot_id])

    def revoke_url(self, bot_id, integration_id):
        return reverse(
            "bots:native-u5-discord-revoke",
            args=[bot_id, integration_id]
        )

    def test_routes_resolve(self):
        from django.urls import resolve

        self.assertEqual(
            resolve(self.api_url()).func.view_class.__name__,
            "NativeApiAccessView"
        )
        self.assertEqual(
            resolve(self.discord_url(1)).func.view_class.__name__,
            "NativeDiscordView"
        )
        self.assertEqual(
            resolve(self.revoke_url(1, 2)).func.view_class.__name__,
            "NativeDiscordRevokeView"
        )

    def test_api_access_requires_authentication(self):
        response = self.client.get(self.api_url())
        self.assertEqual(response.status_code, 401)

    def test_api_access_get_contract(self):
        self.authenticate(self.owner_token)
        response = self.client.get(self.api_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("is_pro", response.data)
        self.assertIsInstance(response.data["is_pro"], bool)

    def test_api_access_rejects_invalid_action(self):
        self.authenticate(self.owner_token)
        response = self.client.post(
            self.api_url(), {"action": "invalid"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_api_access_rejects_free_rotation(self):
        self.authenticate(self.owner_token)
        response = self.client.post(
            self.api_url(), {"action": "rotate"}, format="json"
        )
        self.assertEqual(response.status_code, 403)

    def test_api_access_revoke_contract(self):
        self.authenticate(self.owner_token)
        response = self.client.post(
            self.api_url(), {"action": "revoke"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("message", response.data)
        self.assertNotIn("key", response.data)
        self.assertIn("no-store", response["Cache-Control"])

    def test_discord_requires_authentication(self):
        response = self.client.get(self.discord_url(1))
        self.assertEqual(response.status_code, 401)

    def test_discord_rejects_unknown_bot(self):
        self.authenticate(self.owner_token)
        response = self.client.get(self.discord_url(999999))
        self.assertEqual(response.status_code, 404)

    def test_discord_revoke_requires_authentication(self):
        response = self.client.post(self.revoke_url(1, 1))
        self.assertEqual(response.status_code, 401)

    def test_api_access_response_is_not_cached(self):
        self.authenticate(self.owner_token)
        response = self.client.get(self.api_url())
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])

    def test_discord_rejects_invalid_token_without_bot_access(self):
        self.authenticate(self.owner_token)
        response = self.client.post(
            self.discord_url(999999),
            {"discord_token": "invalid token with spaces"},
            format="json"
        )
        self.assertEqual(response.status_code, 404)
