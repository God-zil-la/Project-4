"""U6.3 step 255B: verified audio completion tests."""

from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import SimpleTestCase

from ai_assistant.voice.models import VoiceTurn
from ai_assistant.voice.real_voice_bridge import (
    execute_real_voice_bridge,
)


class Step255BTests(SimpleTestCase):

    def setUp(self):
        # Provider unit tests isolate session authorization; Block C tests exercise it in the database.
        guard = patch("ai_assistant.voice.service._session")
        guard.start()
        self.addCleanup(guard.stop)
        self.user = Mock()
        self.request_id = uuid4()
        self.session_id = uuid4()
        self.conversation_id = uuid4()
        self.store = object()
        self.synthesize = Mock()

        self.session = SimpleNamespace(
            public_id=self.session_id,
            assistant_id=123,
            conversation=SimpleNamespace(
                public_id=self.conversation_id,
            ),
        )

        self.turn = SimpleNamespace(
            state=VoiceTurn.State.SYNTHESIZING,
            request_id=self.request_id,
            assistant_message_id=456,
            session=self.session,
        )

    def run_bridge(self, tts_result, recovery_result):
        with (
            patch(
                "ai_assistant.voice.real_voice_bridge."
                "voice_service.claim_tts_dispatch",
                return_value=(self.turn, True),
            ),
            patch(
                "ai_assistant.voice.real_voice_bridge."
                "execute_isolated_live_tts",
                return_value=tts_result,
            ),
            patch(
                "ai_assistant.voice.real_voice_bridge."
                "recover_real_voice_audio",
                return_value=recovery_result,
            ) as recover,
        ):
            result = execute_real_voice_bridge(
                user=self.user,
                session_id=self.session_id,
                request_id=self.request_id,
                audio_store=self.store,
                synthesize=self.synthesize,
            )

        return result, recover

    def test_01_verified_audio_completes(self):
        result, recover = self.run_bridge(
            SimpleNamespace(
                state="succeeded",
                request_id=self.request_id,
            ),
            SimpleNamespace(audio_available=True),
        )

        self.assertEqual(
            result.state,
            VoiceTurn.State.COMPLETED,
        )
        self.assertTrue(result.audio_available)
        recover.assert_called_once()

    def test_02_missing_audio_does_not_complete(self):
        result, recover = self.run_bridge(
            SimpleNamespace(
                state="succeeded",
                request_id=self.request_id,
            ),
            SimpleNamespace(audio_available=False),
        )

        self.assertEqual(
            result.state,
            VoiceTurn.State.SYNTHESIZING,
        )
        self.assertFalse(result.audio_available)
        recover.assert_called_once()

    def test_03_uncertain_does_not_recover_or_retry(self):
        result, recover = self.run_bridge(
            SimpleNamespace(
                state="uncertain",
                request_id=self.request_id,
            ),
            None,
        )

        self.assertEqual(result.state, "uncertain")
        self.assertFalse(result.audio_available)
        recover.assert_not_called()

    def test_04_duplicate_claim_does_not_synthesize(self):
        self.turn.state = VoiceTurn.State.SYNTHESIZING

        with (
            patch(
                "ai_assistant.voice.real_voice_bridge."
                "voice_service.claim_tts_dispatch",
                return_value=(self.turn, False),
            ),
            patch(
                "ai_assistant.voice.real_voice_bridge."
                "execute_isolated_live_tts",
            ) as tts,
            patch(
                "ai_assistant.voice.real_voice_bridge."
                "recover_real_voice_audio",
            ) as recover,
        ):
            result = execute_real_voice_bridge(
                user=self.user,
                session_id=self.session_id,
                request_id=self.request_id,
                audio_store=self.store,
                synthesize=self.synthesize,
            )

        self.assertFalse(result.audio_available)
        tts.assert_not_called()
        recover.assert_not_called()

    def test_05_recovery_error_never_completes(self):
        with (
            patch(
                "ai_assistant.voice.real_voice_bridge."
                "voice_service.claim_tts_dispatch",
                return_value=(self.turn, True),
            ),
            patch(
                "ai_assistant.voice.real_voice_bridge."
                "execute_isolated_live_tts",
                return_value=SimpleNamespace(
                    state="succeeded",
                    request_id=self.request_id,
                ),
            ),
            patch(
                "ai_assistant.voice.real_voice_bridge."
                "recover_real_voice_audio",
                side_effect=RuntimeError("storage unavailable"),
            ),
        ):
            with self.assertRaises(RuntimeError):
                execute_real_voice_bridge(
                    user=self.user,
                    session_id=self.session_id,
                    request_id=self.request_id,
                    audio_store=self.store,
                    synthesize=self.synthesize,
                )
