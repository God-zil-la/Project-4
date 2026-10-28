from types import SimpleNamespace
from unittest.mock import patch

from .models import VoiceTurn
from .test_tts_adapter import TTSAdapterTests
from .tts_adapter import synthesize_voice_answer, recover_voice_answer


class TTSRecoveryIntegrationTests(TTSAdapterTests):
    def test_synthesis_exception_keeps_recoverable_state(self):
        self._save_answer()

        with patch(
            "ai_assistant.voice.tts_adapter.synthesize_saved_response",
            side_effect=RuntimeError("storage failure"),
        ) as synth:
            with self.assertRaises(RuntimeError):
                synthesize_voice_answer(**self._kwargs())

        synth.assert_called_once()
        self.turn.refresh_from_db()
        self.assertEqual(self.turn.state, VoiceTurn.State.SYNTHESIZING)

    def test_recovery_does_not_repeat_synthesis(self):
        self._save_answer()

        with patch(
            "ai_assistant.voice.tts_adapter.synthesize_saved_response",
            side_effect=RuntimeError("database failure"),
        ) as synth:
            with self.assertRaises(RuntimeError):
                synthesize_voice_answer(**self._kwargs())

            with patch(
                "ai_assistant.voice.tts_adapter.recover_saved_response",
                return_value=SimpleNamespace(
                    state="succeeded",
                    audio=b"recovered-audio",
                ),
            ) as recover:
                result = recover_voice_answer(
                    **self._kwargs(),
                    audio_store=object(),
                )

        synth.assert_called_once()
        recover.assert_called_once()
        self.assertEqual(result.state, "succeeded")

        self.turn.refresh_from_db()
        self.assertEqual(self.turn.state, VoiceTurn.State.COMPLETED)
