import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_assistant.bots.chat_service import _save_chat_exchange
from ai_assistant.bots.models import Bot, ChatMessage, Conversation
from .models import VoiceTurn
from .service import advance_turn, reserve_turn, start_session


class AtomicBindingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username="u63_atomic_owner")
        cls.other = User.objects.create_user(username="u63_atomic_other")
        cls.bot = Bot.objects.create(
            owner=cls.user, name="Atomic Voice Bot"
        )
        cls.conversation = Conversation.objects.create(
            user=cls.user, bot=cls.bot
        )

    def setUp(self):
        session = start_session(
            user=self.user,
            assistant=self.bot,
            conversation=self.conversation,
        )
        request_id = uuid.uuid4()
        self.turn, _ = reserve_turn(
            user=self.user,
            session_id=session.public_id,
            request_id=request_id,
            audio_sha256="a" * 64,
        )

        for expected, target in (
            (VoiceTurn.State.CREATED, VoiceTurn.State.TRANSCRIBING),
            (VoiceTurn.State.TRANSCRIBING, VoiceTurn.State.TRANSCRIBED),
            (VoiceTurn.State.TRANSCRIBED, VoiceTurn.State.PROCESSING),
        ):
            advance_turn(
                user=self.user,
                session_id=session.public_id,
                request_id=request_id,
                expected=expected,
                target=target,
            )

    def save_exchange(self, **overrides):
        arguments = dict(
            conversation=self.conversation,
            bot=self.bot,
            user=self.user,
            user_message="Voice input",
            assistant_message="AI response",
            voice_turn_id=self.turn.pk,
        )
        arguments.update(overrides)
        return _save_chat_exchange(**arguments)

    def test_successful_atomic_binding(self):
        message_id = self.save_exchange()
        self.turn.refresh_from_db()

        self.assertEqual(
            self.turn.assistant_message_id, message_id
        )
        self.assertEqual(
            self.turn.state, VoiceTurn.State.ANSWER_SAVED
        )
        self.assertEqual(
            ChatMessage.objects.filter(
                conversation=self.conversation
            ).count(),
            2,
        )

    def test_wrong_user_rolls_back_all_messages(self):
        with self.assertRaises(ValueError):
            self.save_exchange(user=self.other)

        self.assertEqual(ChatMessage.objects.count(), 0)
        self.turn.refresh_from_db()
        self.assertEqual(
            self.turn.state, VoiceTurn.State.PROCESSING
        )

    def test_wrong_conversation_rolls_back_messages(self):
        wrong = Conversation.objects.create(
            user=self.user, bot=self.bot
        )

        with self.assertRaises(ValueError):
            self.save_exchange(conversation=wrong)

        self.assertEqual(ChatMessage.objects.count(), 0)

    def test_wrong_state_rolls_back_messages(self):
        self.turn.state = VoiceTurn.State.UNCERTAIN
        self.turn.save(update_fields=["state"])

        with self.assertRaises(ValueError):
            self.save_exchange()

        self.assertEqual(ChatMessage.objects.count(), 0)

    def test_second_save_cannot_duplicate_exchange(self):
        self.save_exchange()

        with self.assertRaises(ValueError):
            self.save_exchange()

        self.assertEqual(ChatMessage.objects.count(), 2)
