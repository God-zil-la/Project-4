from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from ai_assistant.bots.models import Bot, Conversation

from .models import VoiceSession
from .service import (
    VoiceAccessDenied,
    _session,
    expire_voice_session,
    start_session,
)


class VoiceSessionExpiryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.user = user_model.objects.create_user(
            username="u63_expiry_test"
        )
        cls.bot = Bot.objects.create(
            owner=cls.user,
            name="Expiry Test Assistant",
        )
        cls.conversation = Conversation.objects.create(
            user=cls.user,
            bot=cls.bot,
        )

    def test_recent_session_remains_accessible(self):
        session = start_session(
            user=self.user,
            assistant=self.bot,
            conversation=self.conversation,
        )

        found = _session(self.user, session.public_id)

        self.assertEqual(found.pk, session.pk)

    def test_old_session_is_rejected_and_closed(self):
        session = start_session(
            user=self.user,
            assistant=self.bot,
            conversation=self.conversation,
        )

        VoiceSession.objects.filter(pk=session.pk).update(
            created_at=timezone.now() - timedelta(hours=25)
        )


        self.assertEqual(
            expire_voice_session(
                user=self.user,
                session_id=session.public_id,
            ),
            1,
        )

        with self.assertRaises(VoiceAccessDenied):
            _session(self.user, session.public_id)

        session.refresh_from_db()
        self.assertFalse(session.active)
        self.assertIsNotNone(session.ended_at)
