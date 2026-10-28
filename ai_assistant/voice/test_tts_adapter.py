import uuid
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from ai_assistant.bots.chat_service import _save_chat_exchange
from ai_assistant.bots.models import Bot, Conversation

from .models import VoiceTurn
from .service import (
    VoiceAccessDenied,
    VoiceConflict,
    advance_turn,
    claim_ai_dispatch,
    reserve_turn,
    save_transcript,
    start_session,
)
from .tts_adapter import (
    synthesize_voice_answer,
    recover_voice_answer,
)


class TTSAdapterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.user = User.objects.create_user(username="u63_tts_owner")
        cls.other = User.objects.create_user(username="u63_tts_other")
        cls.bot = Bot.objects.create(
            owner=cls.user, name="U63 TTS Bot"
        )
        cls.conversation = Conversation.objects.create(
            user=cls.user, bot=cls.bot
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

    def _kwargs(self, **changes):
        data = dict(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
        )
        data.update(changes)
        return data

    def _save_answer(self):
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
            transcript="Please answer",
        )
        claim_ai_dispatch(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
        )
        return _save_chat_exchange(
            conversation=self.conversation,
            bot=self.bot,
            user=self.user,
            user_message="Please answer",
            assistant_message="Saved AI response",
            voice_turn_id=self.turn.pk,
        )

    def test_saved_answer_passes_correct_ids(self):
        message_id = self._save_answer()

        with patch(
            "ai_assistant.voice.tts_adapter.synthesize_saved_response",
            return_value=SimpleNamespace(state="succeeded"),
        ) as synth:
            synthesize_voice_answer(**self._kwargs())

        synth.assert_called_once()
        values = synth.call_args.kwargs

        self.assertEqual(values["user"], self.user)
        self.assertEqual(values["assistant_id"], self.bot.pk)
        self.assertEqual(
            values["conversation_id"], self.conversation.public_id
        )
        self.assertEqual(values["message_id"], message_id)
        self.assertEqual(values["request_id"], self.request_id)

    def test_unsaved_answer_rejected(self):
        with patch(
            "ai_assistant.voice.tts_adapter.synthesize_saved_response"
        ) as synth:
            with self.assertRaises(VoiceConflict):
                synthesize_voice_answer(**self._kwargs())
            synth.assert_not_called()

    def test_foreign_user_rejected(self):
        self._save_answer()
        with self.assertRaises(VoiceAccessDenied):
            synthesize_voice_answer(
                **self._kwargs(user=self.other)
            )

    def test_missing_turn_rejected(self):
        with self.assertRaises(VoiceAccessDenied):
            synthesize_voice_answer(
                **self._kwargs(request_id=uuid.uuid4())
            )

    def test_recovery_uses_saved_message(self):
        message_id = self._save_answer()

        from .service import claim_tts_dispatch

        turn, claimed = claim_tts_dispatch(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
        )
        self.assertTrue(claimed)
        self.assertEqual(turn.state, VoiceTurn.State.SYNTHESIZING)

        store = object()

        with patch(
            "ai_assistant.voice.tts_adapter.recover_saved_response",
            return_value=SimpleNamespace(state="succeeded"),
        ) as recover:
            recover_voice_answer(
                **self._kwargs(audio_store=store)
            )

        recover.assert_called_once()
        values = recover.call_args.kwargs
        self.assertEqual(values["message_id"], message_id)
        self.assertIs(values["audio_store"], store)
