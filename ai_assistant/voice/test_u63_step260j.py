"""U6.3 trusted integration tests. No paid providers."""

from unittest.mock import patch, sentinel

from django.test import SimpleTestCase

from .service import VoiceConflict
from .trusted_live_integration import execute_trusted_live_voice


class Step260JTrustedIntegrationTests(SimpleTestCase):

    def setUp(self):
        self.arguments = {
            "user": sentinel.user,
            "session_id": sentinel.session_id,
            "request_id": sentinel.request_id,
            "reservation": sentinel.reservation,
            "evidence": sentinel.evidence,
            "audio": sentinel.audio,
            "transcriber": lambda audio: "Test transcription",
            "audio_store": sentinel.audio_store,
            "real_tts_synthesize": lambda text: b"mock-mp3",
        }

    @patch(
        "ai_assistant.voice.trusted_live_integration."
        "execute_live_voice_turn"
    )
    def test_all_dependencies_forwarded(self, pipeline):
        pipeline.return_value = {"state": "completed"}

        result = execute_trusted_live_voice(**self.arguments)

        self.assertEqual(result["state"], "completed")
        pipeline.assert_called_once_with(**self.arguments)

    @patch(
        "ai_assistant.voice.trusted_live_integration."
        "execute_live_voice_turn"
    )
    def test_invalid_transcriber_blocked(self, pipeline):
        self.arguments["transcriber"] = None

        with self.assertRaises(VoiceConflict):
            execute_trusted_live_voice(**self.arguments)

        pipeline.assert_not_called()

    @patch(
        "ai_assistant.voice.trusted_live_integration."
        "execute_live_voice_turn"
    )
    def test_invalid_tts_blocked(self, pipeline):
        self.arguments["real_tts_synthesize"] = object()

        with self.assertRaises(VoiceConflict):
            execute_trusted_live_voice(**self.arguments)

        pipeline.assert_not_called()

    @patch(
        "ai_assistant.voice.trusted_live_integration."
        "execute_live_voice_turn"
    )
    def test_provider_failure_not_retried(self, pipeline):
        pipeline.side_effect = RuntimeError("Mock provider failure")

        with self.assertRaises(RuntimeError):
            execute_trusted_live_voice(**self.arguments)

        pipeline.assert_called_once()

    @patch(
        "ai_assistant.voice.trusted_live_integration."
        "execute_live_voice_turn"
    )
    def test_default_tts_remains_disabled(self, pipeline):
        self.arguments["real_tts_synthesize"] = None

        execute_trusted_live_voice(**self.arguments)

        self.assertIsNone(
            pipeline.call_args.kwargs["real_tts_synthesize"]
        )

    @patch(
        "ai_assistant.voice.trusted_live_integration."
        "execute_live_voice_turn"
    )
    def test_no_automatic_provider_creation(self, pipeline):
        pipeline.return_value = {"state": "transcribed"}

        execute_trusted_live_voice(**self.arguments)

        self.assertEqual(pipeline.call_count, 1)