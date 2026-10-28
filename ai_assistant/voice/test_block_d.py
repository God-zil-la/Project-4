"""Block D endpoint contracts. All providers remain mocked/disabled."""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.authtoken.models import Token

from ai_assistant.bots.models import Bot, Conversation
from .models import VoiceSession, VoiceTurn
from .live_quota_models import LiveVoiceMonthlyUsage, LiveVoiceQuotaReservation
from .test_upload_api import sample_wav


class BlockDSessionAPITests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="block_d_owner")
        self.other = get_user_model().objects.create_user(username="block_d_other")
        self.bot = Bot.objects.create(owner=self.user, name="Block D")
        self.conversation = Conversation.objects.create(user=self.user, bot=self.bot)
        self.now = datetime(2026, 10, 24, 12, tzinfo=timezone.utc)
        self.request_id = str(uuid4())
        self.client.force_login(self.user)

    def start(self, **extra):
        return self.client.post("/api/live-voice/start/", {
            "assistant_id": self.bot.pk,
            "conversation_id": str(self.conversation.public_id),
            "request_id": self.request_id, **extra,
        }, content_type="application/json")

    def test_start_retry_reuses_session_and_reservation(self):
        with patch("django.utils.timezone.now", return_value=self.now):
            first = self.start()
        with patch("django.utils.timezone.now", return_value=self.now + timedelta(seconds=2)):
            second = self.start()
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.json()["session_id"], second.json()["session_id"])
        self.assertEqual(first.json()["deadline_at"], second.json()["deadline_at"])
        self.assertEqual(second.json()["remaining_ms"], 598000)
        self.assertEqual(VoiceSession.objects.count(), 1)
        self.assertEqual(LiveVoiceQuotaReservation.objects.count(), 1)

    def test_retry_cannot_rebind_to_another_conversation(self):
        with patch("django.utils.timezone.now", return_value=self.now):
            self.start()
            other = Conversation.objects.create(user=self.user, bot=self.bot)
            response = self.start(conversation_id=str(other.public_id))
        self.assertEqual(response.status_code, 409)
        self.assertEqual(VoiceSession.objects.count(), 1)

    def test_deadline_status_and_stop_charge_once(self):
        with patch("django.utils.timezone.now", return_value=self.now):
            data = self.start().json()
        url = f'/api/live-voice/{data["session_id"]}/'
        with patch("django.utils.timezone.now", return_value=self.now + timedelta(seconds=600)):
            status = self.client.get(url)
            first = self.client.post(url + "stop/", {"consumed_ms": 0})
            second = self.client.post(url + "stop/")
        self.assertFalse(status.json()["active"])
        self.assertEqual(status.json()["remaining_ms"], 0)
        self.assertEqual(status["Cache-Control"], "no-store")
        self.assertEqual(first.json(), second.json())
        usage = LiveVoiceMonthlyUsage.objects.get(user=self.user)
        self.assertEqual((usage.used_ms, usage.reserved_ms), (600000, 0))
        self.assertTrue(Conversation.objects.filter(pk=self.conversation.pk).exists())

    def test_early_stop_and_replayed_start_do_not_extend_or_recharge(self):
        with patch("django.utils.timezone.now", return_value=self.now):
            data = self.start(remaining_ms=9000000, duration_ms=9000000).json()
        with patch("django.utils.timezone.now", return_value=self.now + timedelta(seconds=3)):
            stop = self.client.post(f'/api/live-voice/{data["session_id"]}/stop/', {"consumed_ms": 0})
            replay = self.start().json()
        self.assertEqual(stop.status_code, 200)
        self.assertEqual(stop.json()["remaining_ms"], 0)
        self.assertFalse(replay["active"])
        usage = LiveVoiceMonthlyUsage.objects.get(user=self.user)
        self.assertEqual((usage.used_ms, usage.reserved_ms), (3000, 0))
        self.assertEqual(VoiceSession.objects.count(), 1)

    def test_foreign_user_cannot_read_or_stop(self):
        with patch("django.utils.timezone.now", return_value=self.now):
            data = self.start().json()
        self.client.force_login(self.other)
        url = f'/api/live-voice/{data["session_id"]}/'
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url + "stop/").status_code, 404)
        self.assertTrue(VoiceSession.objects.get().active)

    def test_legacy_status_and_stop_are_read_only(self):
        legacy = VoiceSession.objects.create(user=self.user, assistant=self.bot, conversation=self.conversation)
        before = dict(VoiceSession.objects.filter(pk=legacy.pk).values().get())
        url = f"/api/live-voice/{legacy.public_id}/"
        with patch("django.utils.timezone.now", return_value=self.now + timedelta(days=10)):
            self.assertEqual(self.client.get(url).status_code, 409)
            self.assertEqual(self.client.post(url + "stop/").status_code, 409)
        self.assertEqual(before, VoiceSession.objects.filter(pk=legacy.pk).values().get())
        self.assertFalse(LiveVoiceMonthlyUsage.objects.exists())

    def test_mobile_token_start_status_stop(self):
        self.client.logout()
        token = Token.objects.create(user=self.user)
        self.client.defaults["HTTP_AUTHORIZATION"] = "Token " + token.key
        with patch("django.utils.timezone.now", return_value=self.now):
            data = self.start().json()
            url = f'/api/live-voice/{data["session_id"]}/'
            self.assertEqual(self.client.get(url).status_code, 200)
            self.assertEqual(self.client.post(url + "stop/").status_code, 200)

    def test_prepare_only_never_resolves_external_dependencies(self):
        with patch("django.utils.timezone.now", return_value=self.now):
            data = self.start().json()
            with patch("ai_assistant.voice.upload_api.resolve_http_voice_dependencies") as external:
                response = self.client.post(f'/api/live-voice/{data["session_id"]}/upload/', {
                    "request_id": str(uuid4()), "prepare_only": "true",
                    "audio": SimpleUploadedFile("test.wav", sample_wav(), content_type="audio/wav"),
                })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["state"], "created")
        external.assert_not_called()
        self.assertEqual(VoiceTurn.objects.count(), 1)
