"""U6.3 read-only voice-turn status API tests."""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from ai_assistant.bots.models import Bot, Conversation
from .models import VoiceTurn
from .service import start_session, reserve_turn


class VoiceTurnStatusAPITests(TestCase):

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="u63_status_owner",
            password="test-password-123",
        )
        self.other = User.objects.create_user(
            username="u63_status_other",
            password="test-password-123",
        )
        self.bot = Bot.objects.create(
            owner=self.user,
            name="Voice status test",
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
        self.request_id = uuid.uuid4()
        self.turn, _ = reserve_turn(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
            audio_sha256="a" * 64,
        )
        self.url = reverse(
            "voice-turn-status",
            kwargs={
                "session_id": self.session.public_id,
                "request_id": self.request_id,
            },
        )

    def test_owner_can_read_status(self):
        self.client.force_login(self.user)
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["state"],
            VoiceTurn.State.CREATED,
        )
        self.assertFalse(response.json()["has_transcript"])
        self.assertFalse(response.json()["has_assistant_answer"])
        self.assertNotIn("transcript", response.json())

    def test_anonymous_user_is_rejected(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 401)

    def test_other_user_cannot_read_status(self):
        self.client.force_login(self.other)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_unknown_turn_is_rejected(self):
        self.client.force_login(self.user)
        unknown_url = reverse(
            "voice-turn-status",
            kwargs={
                "session_id": self.session.public_id,
                "request_id": uuid.uuid4(),
            },
        )
        response = self.client.get(unknown_url)
        self.assertEqual(response.status_code, 404)

    def test_closed_session_is_rejected(self):
        self.session.active = False
        self.session.save(update_fields=["active"])

        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 404)

    def test_post_is_not_allowed(self):
        self.client.force_login(self.user)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 405)
