from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from ai_assistant.voice import orchestrator
from ai_assistant.voice.models import VoiceTurn


class Step256CIntegrationTests(TestCase):

    def setUp(self):
        self.user = SimpleNamespace(pk=101)
        self.session = SimpleNamespace(
            public_id="session-256c",
        )
        self.turn = SimpleNamespace(
            pk=501,
            request_id="request-256c",
            state=VoiceTurn.State.ANSWER_SAVED,
            assistant_message_id=601,
        )
        self.turn.refresh_from_db = lambda: None

    def run_orchestrator(self, synthesizer=None):
        with (
            patch.object(
                orchestrator,
                "_session",
                return_value=self.session,
            ),
            patch.object(
                orchestrator,
                "_uuid",
                return_value=self.turn.request_id,
            ),
            patch.object(
                orchestrator.VoiceTurn.objects,
                "filter",
            ) as query,
            patch.object(
                orchestrator,
                "execute_real_voice_bridge",
                return_value=SimpleNamespace(
                    state=VoiceTurn.State.COMPLETED,
                    audio_available=True,
                ),
            ) as real_bridge,
            patch.object(
                orchestrator,
                "synthesize_voice_answer",
                return_value=SimpleNamespace(
                    state=VoiceTurn.State.COMPLETED,
                    audio=b"mock-audio",
                ),
            ) as legacy_tts,
        ):
            query.return_value.first.return_value = self.turn

            result = orchestrator.continue_voice_turn(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.turn.request_id,
                audio_store=object(),
                real_tts_synthesize=synthesizer,
            )

            return result, real_bridge.call_count, legacy_tts.call_count

    def test_01_opt_in_calls_real_bridge(self):
        result, real_calls, legacy_calls = self.run_orchestrator(
            synthesizer=lambda text: b"mp3"
        )
        self.assertEqual(real_calls, 1)
        self.assertEqual(legacy_calls, 0)
        self.assertTrue(result["audio_available"])
        self.assertEqual(result["state"], VoiceTurn.State.COMPLETED)

    def test_02_default_preserves_legacy(self):
        result, real_calls, legacy_calls = self.run_orchestrator()
        self.assertEqual(real_calls, 0)
        self.assertEqual(legacy_calls, 1)
        self.assertEqual(result["audio"], b"mock-audio")

    def test_03_no_automatic_paid_provider(self):
        result, real_calls, legacy_calls = self.run_orchestrator()
        self.assertEqual(real_calls, 0)
        self.assertEqual(legacy_calls, 1)

    def test_04_real_path_returns_no_raw_audio(self):
        result, real_calls, legacy_calls = self.run_orchestrator(
            synthesizer=lambda text: b"mp3"
        )
        self.assertEqual(real_calls, 1)
        self.assertIsNone(result["audio"])

    def test_05_missing_audio_is_not_reported_ready(self):
        with (
            patch.object(orchestrator, "_session", return_value=self.session),
            patch.object(orchestrator, "_uuid", return_value=self.turn.request_id),
            patch.object(orchestrator.VoiceTurn.objects, "filter") as query,
            patch.object(
                orchestrator,
                "execute_real_voice_bridge",
                return_value=SimpleNamespace(
                    state=VoiceTurn.State.SYNTHESIZING,
                    audio_available=False,
                ),
            ),
        ):
            query.return_value.first.return_value = self.turn
            result = orchestrator.continue_voice_turn(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.turn.request_id,
                audio_store=object(),
                real_tts_synthesize=lambda text: b"mp3",
            )

        self.assertFalse(result["audio_available"])
        self.assertEqual(result["state"], VoiceTurn.State.SYNTHESIZING)
