import uuid
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_assistant.bots.chat_service import _save_chat_exchange
from ai_assistant.bots.models import Bot, ChatMessage, Conversation

from .models import VoiceTurn
from .orchestrator import continue_voice_turn
from .service import (
    VoiceConflict,
    advance_turn,
    reserve_turn,
    save_transcript,
    start_session,
)


class OrchestratorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username="u63_orchestrator")
        cls.bot = Bot.objects.create(
            owner=cls.user,
            name="Voice Orchestrator Bot",
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
            transcript="Hello AI",
        )

    def run_turn(self, **changes):
        args = dict(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
        )
        args.update(changes)
        return continue_voice_turn(**args)

    def fake_chat(self, **kwargs):
        message_id = _save_chat_exchange(
            conversation=self.conversation,
            bot=self.bot,
            user=self.user,
            user_message=kwargs["message"],
            assistant_message="Hello back",
            voice_turn_id=kwargs["voice_turn_id"],
        )
        return {"assistant_message_id": message_id}

    def test_full_turn_saves_answer_and_completes(self):
        with patch(
            "ai_assistant.voice.ai_adapter.process_bot_message",
            side_effect=self.fake_chat,
        ) as chat, patch(
            "ai_assistant.voice.tts_adapter.synthesize_saved_response",
            return_value=SimpleNamespace(
                state="succeeded",
                audio=b"fake-audio",
            ),
        ) as tts:
            result = self.run_turn()

        self.assertEqual(chat.call_count, 1)
        self.assertEqual(tts.call_count, 1)
        self.assertEqual(result["state"], "succeeded")

        self.turn.refresh_from_db()
        self.assertEqual(self.turn.state, VoiceTurn.State.COMPLETED)
        self.assertIsNotNone(self.turn.assistant_message_id)

        self.assertEqual(
            ChatMessage.objects.filter(
                conversation=self.conversation
            ).count(),
            2,
        )

    def test_replay_does_not_generate_second_answer(self):
        with patch(
            "ai_assistant.voice.ai_adapter.process_bot_message",
            side_effect=self.fake_chat,
        ) as chat, patch(
            "ai_assistant.voice.tts_adapter.synthesize_saved_response",
            return_value=SimpleNamespace(
                state="succeeded",
                audio=b"fake-audio",
            ),
        ) as tts:
            self.run_turn()
            repeated = self.run_turn()

        self.assertEqual(chat.call_count, 1)
        self.assertEqual(tts.call_count, 1)
        self.assertEqual(repeated["state"], VoiceTurn.State.COMPLETED)

    def test_cannot_continue_before_transcription(self):
        self.turn.state = VoiceTurn.State.CREATED
        self.turn.save(update_fields=["state"])

        with self.assertRaises(VoiceConflict):
            self.run_turn()
