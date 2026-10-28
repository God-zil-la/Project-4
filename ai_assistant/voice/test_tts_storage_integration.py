import uuid
from contextlib import ExitStack
from unittest.mock import patch

from django.test import TransactionTestCase
from django.contrib.auth import get_user_model

from ai_assistant.bots.chat_service import _save_chat_exchange
from ai_assistant.bots.models import Bot, Conversation
from ai_assistant.tts import authorization, saved_service, saved_synthesis, service
from ai_assistant.tts.audio_store_memory import MemoryAudioStore
from ai_assistant.tts.models import TTSRequest

from .models import VoiceTurn
from .service import (
    advance_turn,
    claim_ai_dispatch,
    reserve_turn,
    save_transcript,
    start_session,
)
from .tts_adapter import synthesize_voice_answer, recover_voice_answer


class VoiceTTSStorageIntegrationTests(TransactionTestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="u63_storage_owner"
        )
        self.bot = Bot.objects.create(
            owner=self.user,
            name="U63 Storage Bot",
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
        self.store = MemoryAudioStore()

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
            transcript="Please answer",
        )
        claim_ai_dispatch(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
        )

        _save_chat_exchange(
            conversation=self.conversation,
            bot=self.bot,
            user=self.user,
            user_message="Please answer",
            assistant_message="Saved AI response",
            voice_turn_id=self.turn.pk,
        )

        self.stack = ExitStack()
        self.addCleanup(self.stack.close)

        self.stack.enter_context(
            patch.object(
                authorization,
                "_effective_plan",
                return_value="premium",
            )
        )
        self.stack.enter_context(
            patch.object(
                authorization,
                "_owns_assistant",
                return_value=True,
            )
        )
        self.stack.enter_context(
            patch.object(
                saved_service,
                "get_assistant_message",
                return_value="Saved AI response",
            )
        )
        self.stack.enter_context(
            patch.object(
                saved_synthesis,
                "get_assistant_message",
                return_value="Saved AI response",
            )
        )

        self.provider = self.stack.enter_context(
            patch.object(
                saved_synthesis.MockProvider,
                "synthesize",
                return_value=b"mock-audio",
            )
        )

    def kwargs(self):
        return dict(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
            audio_store=self.store,
        )

    def test_success_stores_audio_and_completes_voice_turn(self):
        result = synthesize_voice_answer(**self.kwargs())

        self.assertEqual(result.state, "succeeded")
        self.assertEqual(result.audio, b"mock-audio")

        self.turn.refresh_from_db()
        self.assertEqual(
            self.turn.state,
            VoiceTurn.State.COMPLETED,
        )

        row = TTSRequest.objects.get()
        self.assertEqual(row.state, "succeeded")
        self.assertEqual(
            self.store.load(request_id=row.pk),
            b"mock-audio",
        )

        self.provider.assert_called_once()

    def test_database_failure_recovers_without_resynthesis(self):
        with patch.object(
            service,
            "finish",
            side_effect=RuntimeError("commit failed"),
        ):
            with self.assertRaises(RuntimeError):
                synthesize_voice_answer(**self.kwargs())

        self.turn.refresh_from_db()
        self.assertEqual(
            self.turn.state,
            VoiceTurn.State.SYNTHESIZING,
        )

        row = TTSRequest.objects.get()
        self.assertEqual(row.state, "dispatched")
        self.assertEqual(
            self.store.load(request_id=row.pk),
            b"mock-audio",
        )

        result = recover_voice_answer(**self.kwargs())

        self.assertEqual(result.state, "succeeded")
        self.assertEqual(result.audio, b"mock-audio")

        self.turn.refresh_from_db()
        self.assertEqual(
            self.turn.state,
            VoiceTurn.State.COMPLETED,
        )

        self.provider.assert_called_once()

    def test_storage_failure_does_not_resynthesize(self):
        with patch.object(
            self.store,
            "save",
            side_effect=OSError("storage unavailable"),
        ):
            with self.assertRaises(OSError):
                synthesize_voice_answer(**self.kwargs())

        self.turn.refresh_from_db()
        self.assertEqual(
            self.turn.state,
            VoiceTurn.State.SYNTHESIZING,
        )

        row = TTSRequest.objects.get()
        self.assertEqual(row.state, "uncertain")

        result = recover_voice_answer(**self.kwargs())

        self.assertEqual(result.state, "uncertain")
        self.assertIsNone(result.audio)

        self.provider.assert_called_once()
