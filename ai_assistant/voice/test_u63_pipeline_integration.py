from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch, sentinel

from ai_assistant.voice.live_pipeline import execute_live_voice_turn
from ai_assistant.voice.models import VoiceTurn
from ai_assistant.voice.service import VoiceConflict


class LiveVoicePipelineIntegrationTests(TestCase):

    @patch("ai_assistant.voice.live_pipeline.continue_voice_turn")
    @patch("ai_assistant.voice.live_pipeline.execute_testable_stt")
    def test_successful_stt_continues_to_voice(
        self, mock_stt, mock_continue
    ):
        mock_stt.return_value = SimpleNamespace(
            state=VoiceTurn.State.TRANSCRIBED,
            transcript="Hello from STT",
        )
        mock_continue.return_value = {
            "state": VoiceTurn.State.COMPLETED,
            "audio_available": True,
        }

        result = execute_live_voice_turn(
            user=sentinel.user,
            session_id=sentinel.session,
            request_id=sentinel.request,
            reservation=sentinel.reservation,
            evidence=sentinel.evidence,
            audio=sentinel.audio,
            transcriber=sentinel.transcriber,
            audio_store=sentinel.store,
            real_tts_synthesize=sentinel.synthesizer,
        )

        mock_stt.assert_called_once()
        mock_continue.assert_called_once_with(
            user=sentinel.user,
            session_id=sentinel.session,
            request_id=sentinel.request,
            audio_store=sentinel.store,
            real_tts_synthesize=sentinel.synthesizer,
        )
        self.assertEqual(result["voice"]["audio_available"], True)

    @patch("ai_assistant.voice.live_pipeline.continue_voice_turn")
    @patch("ai_assistant.voice.live_pipeline.execute_testable_stt")
    def test_failed_stt_never_reaches_voice(
        self, mock_stt, mock_continue
    ):
        mock_stt.return_value = SimpleNamespace(
            state="failed",
            transcript=None,
        )

        with self.assertRaises(VoiceConflict):
            execute_live_voice_turn(
                user=sentinel.user,
                session_id=sentinel.session,
                request_id=sentinel.request,
                reservation=sentinel.reservation,
                evidence=sentinel.evidence,
                audio=sentinel.audio,
                transcriber=sentinel.transcriber,
                audio_store=sentinel.store,
                real_tts_synthesize=sentinel.synthesizer,
            )

        mock_continue.assert_not_called()
