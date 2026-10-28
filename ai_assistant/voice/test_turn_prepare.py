"""Tests for internal U6.3 voice-turn preparation."""

from types import SimpleNamespace
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_assistant.bots.models import Bot, Conversation
from .models import VoiceTurn
from .service import VoiceAccessDenied, VoiceConflict, start_session
from .turn_prepare import prepare_voice_turn


class VoiceTurnPreparationTests(TestCase):

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="u63_prepare_owner",
            password="test-password",
        )
        self.other = User.objects.create_user(
            username="u63_prepare_other",
            password="test-password",
        )
        self.bot = Bot.objects.create(
            owner=self.user,
            name="U6.3 preparation test",
        )
        self.conversation = Conversation.objects.create(
            user=self.user,
            bot=self.bot,
        )
        self.session = start_session(
            user=self.user,
            assistant=self.bot,
            conversation=self.conversation,
        )
        self.request_id = uuid4()
        self.audio = SimpleNamespace(
            sha256="a" * 64,
            milliseconds=1000,
        )

    def prepare(self, **overrides):
        values = {
            "user": self.user,
            "session_id": self.session.public_id,
            "request_id": self.request_id,
            "audio": self.audio,
        }
        values.update(overrides)
        return prepare_voice_turn(**values)

    def test_creates_turn(self):
        turn, created = self.prepare()

        self.assertTrue(created)
        self.assertEqual(turn.state, VoiceTurn.State.CREATED)
        self.assertEqual(VoiceTurn.objects.count(), 1)

    def test_identical_request_is_idempotent(self):
        first, created = self.prepare()
        second, created_again = self.prepare()

        self.assertTrue(created)
        self.assertFalse(created_again)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(VoiceTurn.objects.count(), 1)

    def test_different_audio_same_request_is_rejected(self):
        self.prepare()

        with self.assertRaises(VoiceConflict):
            self.prepare(audio=SimpleNamespace(
                sha256="b" * 64,
                milliseconds=1000,
            ))

    def test_other_user_is_rejected(self):
        with self.assertRaises(VoiceAccessDenied):
            self.prepare(user=self.other)

        self.assertEqual(VoiceTurn.objects.count(), 0)

    def test_invalid_duration_is_rejected(self):
        with self.assertRaises(VoiceAccessDenied):
            self.prepare(audio=SimpleNamespace(
                sha256="a" * 64,
                milliseconds=0,
            ))

        self.assertEqual(VoiceTurn.objects.count(), 0)

    def test_closed_session_is_rejected(self):
        self.session.active = False
        self.session.save(update_fields=["active"])

        with self.assertRaises(VoiceAccessDenied):
            self.prepare()

        self.assertEqual(VoiceTurn.objects.count(), 0)
