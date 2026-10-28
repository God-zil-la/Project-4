from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from ai_assistant.voice import live_pipeline
from ai_assistant.voice.models import VoiceTurn
from ai_assistant.voice.service import VoiceConflict


class Step257APipelineTests(TestCase):

    def setUp(self):
        self.user = SimpleNamespace(pk=101)
        self.reservation = object()
        self.evidence = object()
        self.audio = object()
        self.transcriber = lambda audio: "Hello"
        self.store = object()

    def execute(self, *, state, synthesizer=None):
        with (
            patch.object(
                live_pipeline,
                "execute_testable_stt",
                return_value=SimpleNamespace(
                    state=state,
                    transcript="Hello",
                ),
            ) as stt,
            patch.object(
                live_pipeline,
                "continue_voice_turn",
                return_value={
                    "state": VoiceTurn.State.COMPLETED,
                    "audio_available": True,
                },
            ) as voice,
        ):
            result = live_pipeline.execute_live_voice_turn(
                user=self.user,
                session_id="session-257a",
                request_id="request-257a",
                reservation=self.reservation,
                evidence=self.evidence,
                audio=self.audio,
                transcriber=self.transcriber,
                audio_store=self.store,
                real_tts_synthesize=synthesizer,
            )
            return result, stt, voice

    def test_01_real_synthesizer_forwarded(self):
        synth = lambda text: b"test-mp3"

        result, stt, voice = self.execute(
            state=VoiceTurn.State.TRANSCRIBED,
            synthesizer=synth,
        )

        self.assertEqual(stt.call_count, 1)
        self.assertEqual(voice.call_count, 1)
        self.assertIs(
            voice.call_args.kwargs["real_tts_synthesize"],
            synth,
        )
        self.assertEqual(
            result["voice"]["state"],
            VoiceTurn.State.COMPLETED,
        )

    def test_02_default_remains_disabled(self):
        result, stt, voice = self.execute(
            state=VoiceTurn.State.TRANSCRIBED,
        )
        self.assertIsNone(
            voice.call_args.kwargs["real_tts_synthesize"]
        )

    def test_03_failed_stt_does_not_continue(self):
        with (
            patch.object(
                live_pipeline,
                "execute_testable_stt",
                return_value=SimpleNamespace(
                    state=VoiceTurn.State.FAILED,
                    transcript="",
                ),
            ),
            patch.object(
                live_pipeline,
                "continue_voice_turn",
            ) as voice,
        ):
            with self.assertRaises(VoiceConflict):
                live_pipeline.execute_live_voice_turn(
                    user=self.user,
                    session_id="session-257a",
                    request_id="request-257a",
                    reservation=self.reservation,
                    evidence=self.evidence,
                    audio=self.audio,
                    transcriber=self.transcriber,
                    audio_store=self.store,
                    real_tts_synthesize=lambda text: b"unused",
                )

            voice.assert_not_called()

    def test_04_uncertain_stt_does_not_continue(self):
        with (
            patch.object(
                live_pipeline,
                "execute_testable_stt",
                return_value=SimpleNamespace(
                    state=VoiceTurn.State.UNCERTAIN,
                    transcript="",
                ),
            ),
            patch.object(
                live_pipeline,
                "continue_voice_turn",
            ) as voice,
        ):
            with self.assertRaises(VoiceConflict):
                live_pipeline.execute_live_voice_turn(
                    user=self.user,
                    session_id="session-257a",
                    request_id="request-257a",
                    reservation=self.reservation,
                    evidence=self.evidence,
                    audio=self.audio,
                    transcriber=self.transcriber,
                    audio_store=self.store,
                    real_tts_synthesize=lambda text: b"unused",
                )

            voice.assert_not_called()

    def test_05_transcript_is_preserved(self):
        result, stt, voice = self.execute(
            state=VoiceTurn.State.TRANSCRIBED,
        )
        self.assertEqual(result["transcript"], "Hello")

    def test_06_store_is_forwarded(self):
        result, stt, voice = self.execute(
            state=VoiceTurn.State.TRANSCRIBED,
        )
        self.assertIs(
            voice.call_args.kwargs["audio_store"],
            self.store,
        )
