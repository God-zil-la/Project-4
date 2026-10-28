import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_assistant.bots.models import Bot, Conversation
from .models import VoiceSession, VoiceTurn
from .service import VoiceAccessDenied, VoiceConflict, reserve_turn, start_session


class VoiceDatabaseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(
            username="u63_owner",
            password="TestOnlyPassword123!",
        )
        cls.stranger = User.objects.create_user(
            username="u63_stranger",
            password="TestOnlyPassword123!",
        )

        cls.bot = Bot.objects.create(
            owner=cls.user,
            name="U63 Test Assistant",
        )

        cls.conversation = Conversation.objects.create(
            user=cls.user,
            bot=cls.bot,
        )

    def test_session_ownership(self):
        session = start_session(
            user=self.user,
            assistant=self.bot,
            conversation=self.conversation,
        )

        self.assertEqual(session.user_id, self.user.pk)
        self.assertEqual(session.assistant_id, self.bot.pk)
        self.assertEqual(
            session.conversation_id,
            self.conversation.pk,
        )

    def test_same_request_creates_one_turn(self):
        session = start_session(
            user=self.user,
            assistant=self.bot,
            conversation=self.conversation,
        )
        request_id = uuid.uuid4()

        first, created_first = reserve_turn(
            user=self.user,
            session_id=session.public_id,
            request_id=request_id,
            audio_sha256="a" * 64,
        )

        second, created_second = reserve_turn(
            user=self.user,
            session_id=session.public_id,
            request_id=request_id,
            audio_sha256="a" * 64,
        )

        self.assertTrue(created_first)
        self.assertFalse(created_second)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            VoiceTurn.objects.filter(
                session=session,
                request_id=request_id,
            ).count(),
            1,
        )

    def test_same_request_different_audio_rejected(self):
        session = start_session(
            user=self.user,
            assistant=self.bot,
            conversation=self.conversation,
        )
        request_id = uuid.uuid4()

        reserve_turn(
            user=self.user,
            session_id=session.public_id,
            request_id=request_id,
            audio_sha256="a" * 64,
        )

        with self.assertRaises(VoiceConflict):
            reserve_turn(
                user=self.user,
                session_id=session.public_id,
                request_id=request_id,
                audio_sha256="b" * 64,
            )

    def test_foreign_user_cannot_reserve_turn(self):
        session = start_session(
            user=self.user,
            assistant=self.bot,
            conversation=self.conversation,
        )

        with self.assertRaises(VoiceAccessDenied):
            reserve_turn(
                user=self.stranger,
                session_id=session.public_id,
                request_id=uuid.uuid4(),
                audio_sha256="a" * 64,
            )
