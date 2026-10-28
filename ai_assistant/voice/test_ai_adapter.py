import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_assistant.bots.models import Bot, ChatMessage, Conversation

from .ai_adapter import process_voice_answer
from .models import VoiceTurn
from .service import (
    VoiceAccessDenied,
    VoiceConflict,
    advance_turn,
    reserve_turn,
    save_transcript,
    start_session,
)


class AIAdapterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(
            username="u63_ai_adapter_owner"
        )
        cls.other = User.objects.create_user(
            username="u63_ai_adapter_other"
        )
        cls.bot = Bot.objects.create(
            owner=cls.user,
            name="U63 AI Test Bot",
        )
        cls.conversation = Conversation.objects.create(
            user=cls.user,
            bot=cls.bot,
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

        advance_turn(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
            expected=VoiceTurn.State.CREATED,
            target=VoiceTurn.State.TRANSCRIBING,
        )

        save_transcript(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
            transcript="Tell me something useful",
        )

    def invoke(self, **changes):
        data = dict(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
        )
        data.update(changes)
        return process_voice_answer(**data)

    def test_success_binds_saved_answer(self):
        def fake_chat(**kwargs):
            from ai_assistant.bots.chat_service import _save_chat_exchange
            message_id = _save_chat_exchange(
                conversation=self.conversation,
                bot=self.bot,
                user=self.user,
                user_message=kwargs["message"],
                assistant_message="Useful answer",
                voice_turn_id=kwargs["voice_turn_id"],
            )
            return {"assistant_message_id": message_id}

        with patch(
            "ai_assistant.voice.ai_adapter.process_bot_message",
            side_effect=fake_chat,
        ) as chat:
            result = self.invoke()

        self.assertEqual(chat.call_count, 1)
        self.assertEqual(result["status"], "saved")
        self.assertFalse(result["reused"])
        self.turn.refresh_from_db()
        self.assertEqual(self.turn.state, VoiceTurn.State.ANSWER_SAVED)
        self.assertIsNotNone(self.turn.assistant_message_id)

    def test_replay_uses_saved_message(self):
        def fake_chat(**kwargs):
            from ai_assistant.bots.chat_service import _save_chat_exchange
            message_id = _save_chat_exchange(
                conversation=self.conversation,
                bot=self.bot,
                user=self.user,
                user_message=kwargs["message"],
                assistant_message="Useful answer",
                voice_turn_id=kwargs["voice_turn_id"],
            )
            return {"assistant_message_id": message_id}

        with patch(
            "ai_assistant.voice.ai_adapter.process_bot_message",
            side_effect=fake_chat,
        ) as chat:
            self.invoke()
            second = self.invoke()

        self.assertEqual(chat.call_count, 1)
        self.assertTrue(second["reused"])
        self.assertEqual(
            ChatMessage.objects.filter(
                conversation=self.conversation
            ).count(), 2
        )

    def test_provider_error_is_not_automatically_retried(self):
        with patch(
            "ai_assistant.voice.ai_adapter.process_bot_message",
            side_effect=RuntimeError("Provider unavailable"),
        ) as chat:
            with self.assertRaises(RuntimeError):
                self.invoke()

            with self.assertRaises(VoiceConflict):
                self.invoke()

        self.assertEqual(chat.call_count, 1)
        self.turn.refresh_from_db()
        self.assertEqual(self.turn.state, VoiceTurn.State.PROCESSING)

    def test_foreign_user_is_rejected(self):
        with self.assertRaises(VoiceAccessDenied):
            self.invoke(user=self.other)

    def test_missing_turn_is_rejected(self):
        with self.assertRaises(VoiceAccessDenied):
            self.invoke(request_id=uuid.uuid4())
