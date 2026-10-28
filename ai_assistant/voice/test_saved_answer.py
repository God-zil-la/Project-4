import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_assistant.bots.models import Bot, ChatMessage, Conversation
from .models import VoiceTurn
from .service import (
    VoiceAccessDenied,
    VoiceConflict,
    advance_turn,
    attach_saved_answer,
    reserve_turn,
    start_session,
)


class VoiceSavedAnswerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username="u63_answer_owner")
        cls.other = User.objects.create_user(username="u63_answer_other")
        cls.bot = Bot.objects.create(
            owner=cls.user, name="Voice Answer Bot"
        )
        cls.conversation = Conversation.objects.create(
            user=cls.user, bot=cls.bot
        )
        cls.other_conversation = Conversation.objects.create(
            user=cls.other, bot=cls.bot
        )

    def setUp(self):
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
        for expected, target in (
            (VoiceTurn.State.CREATED, VoiceTurn.State.TRANSCRIBING),
            (VoiceTurn.State.TRANSCRIBING, VoiceTurn.State.TRANSCRIBED),
            (VoiceTurn.State.TRANSCRIBED, VoiceTurn.State.PROCESSING),
        ):
            advance_turn(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.request_id,
                expected=expected,
                target=target,
            )

        self.message = ChatMessage.objects.create(
            user=self.user,
            bot=self.bot,
            conversation=self.conversation,
            sender=ChatMessage.SENDER_ASSISTANT,
            message="Voice test response",
        )

    def test_attach_valid_answer(self):
        turn, created = attach_saved_answer(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
            message_id=self.message.pk,
        )
        self.assertTrue(created)
        self.assertEqual(turn.assistant_message_id, self.message.pk)
        self.assertEqual(turn.state, VoiceTurn.State.ANSWER_SAVED)

    def test_same_answer_is_idempotent(self):
        arguments = dict(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
            message_id=self.message.pk,
        )
        attach_saved_answer(**arguments)
        turn, created = attach_saved_answer(**arguments)
        self.assertFalse(created)
        self.assertEqual(turn.assistant_message_id, self.message.pk)

    def test_foreign_message_is_rejected(self):
        foreign = ChatMessage.objects.create(
            user=self.other,
            bot=self.bot,
            conversation=self.other_conversation,
            sender=ChatMessage.SENDER_ASSISTANT,
            message="Other person's response",
        )
        with self.assertRaises(VoiceAccessDenied):
            attach_saved_answer(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.request_id,
                message_id=foreign.pk,
            )

    def test_wrong_sender_is_rejected(self):
        user_message = ChatMessage.objects.create(
            user=self.user,
            bot=self.bot,
            conversation=self.conversation,
            sender=ChatMessage.SENDER_USER,
            message="Hello",
        )
        with self.assertRaises(VoiceAccessDenied):
            attach_saved_answer(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.request_id,
                message_id=user_message.pk,
            )

    def test_different_answer_cannot_replace_saved_answer(self):
        another = ChatMessage.objects.create(
            user=self.user,
            bot=self.bot,
            conversation=self.conversation,
            sender=ChatMessage.SENDER_ASSISTANT,
            message="Different response",
        )
        attach_saved_answer(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
            message_id=self.message.pk,
        )
        with self.assertRaises(VoiceConflict):
            attach_saved_answer(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.request_id,
                message_id=another.pk,
            )
