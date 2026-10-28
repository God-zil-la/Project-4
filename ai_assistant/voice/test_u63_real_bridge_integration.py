from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch, sentinel
from uuid import UUID

from ai_assistant.voice.models import VoiceTurn
from ai_assistant.voice.real_voice_bridge import execute_real_voice_bridge


REQUEST_ID = UUID("00000000-0000-0000-0000-000000000063")


class RealVoiceBridgeIntegrationTests(TestCase):
    def setUp(self):
        # Provider unit tests isolate session authorization; Block C tests exercise it in the database.
        guard = patch("ai_assistant.voice.service._session")
        guard.start()
        self.addCleanup(guard.stop)

    def make_turn(self):
        conversation = SimpleNamespace(public_id=sentinel.conversation_id)
        session = SimpleNamespace(
            assistant_id=sentinel.assistant_id,
            conversation=conversation,
            public_id=sentinel.session_id,
        )
        return SimpleNamespace(
            session=session,
            request_id=REQUEST_ID,
            assistant_message_id=sentinel.message_id,
            state=VoiceTurn.State.SYNTHESIZING,
        )

    @patch("ai_assistant.voice.real_voice_bridge.recover_real_voice_audio")
    @patch("ai_assistant.voice.real_voice_bridge.execute_isolated_live_tts")
    @patch("ai_assistant.voice.real_voice_bridge.voice_service.claim_tts_dispatch")
    def test_successful_tts_with_audio_completes(
        self, mock_claim, mock_tts, mock_recover
    ):
        mock_claim.return_value = (self.make_turn(), True)
        mock_tts.return_value = SimpleNamespace(state="succeeded")
        mock_recover.return_value = SimpleNamespace(audio_available=True)

        result = execute_real_voice_bridge(
            user=sentinel.user,
            session_id=sentinel.session_id,
            request_id=REQUEST_ID,
            audio_store=sentinel.store,
            synthesize=lambda text: b'mocked-audio',
        )

        self.assertEqual(result.state, VoiceTurn.State.COMPLETED)
        self.assertTrue(result.audio_available)
        mock_tts.assert_called_once()
        mock_recover.assert_called_once()

    @patch("ai_assistant.voice.real_voice_bridge.recover_real_voice_audio")
    @patch("ai_assistant.voice.real_voice_bridge.execute_isolated_live_tts")
    @patch("ai_assistant.voice.real_voice_bridge.voice_service.claim_tts_dispatch")
    def test_successful_tts_without_audio_does_not_complete(
        self, mock_claim, mock_tts, mock_recover
    ):
        mock_claim.return_value = (self.make_turn(), True)
        mock_tts.return_value = SimpleNamespace(state="succeeded")
        mock_recover.return_value = SimpleNamespace(audio_available=False)

        result = execute_real_voice_bridge(
            user=sentinel.user,
            session_id=sentinel.session_id,
            request_id=REQUEST_ID,
            audio_store=sentinel.store,
            synthesize=lambda text: b'mocked-audio',
        )

        self.assertEqual(result.state, VoiceTurn.State.SYNTHESIZING)
        self.assertFalse(result.audio_available)
        mock_tts.assert_called_once()
        mock_recover.assert_called_once()

    @patch("ai_assistant.voice.real_voice_bridge.recover_real_voice_audio")
    @patch("ai_assistant.voice.real_voice_bridge.execute_isolated_live_tts")
    @patch("ai_assistant.voice.real_voice_bridge.voice_service.claim_tts_dispatch")
    def test_duplicate_dispatch_does_not_repeat_tts(
        self, mock_claim, mock_tts, mock_recover
    ):
        mock_claim.return_value = (self.make_turn(), False)

        result = execute_real_voice_bridge(
            user=sentinel.user,
            session_id=sentinel.session_id,
            request_id=REQUEST_ID,
            audio_store=sentinel.store,
            synthesize=lambda text: b'mocked-audio',
        )

        self.assertFalse(result.audio_available)
        mock_tts.assert_not_called()
        mock_recover.assert_not_called()
