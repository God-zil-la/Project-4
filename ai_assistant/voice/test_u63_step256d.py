from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from ai_assistant.voice import orchestrator
from ai_assistant.voice.models import VoiceTurn
from ai_assistant.voice.service import VoiceConflict


class Step256DRecoveryTests(TestCase):

    def setUp(self):
        self.user = SimpleNamespace(pk=101)
        self.session = SimpleNamespace(public_id="session-256d")
        self.store = object()
        self.turn = SimpleNamespace(
            pk=501,
            request_id="request-256d",
            state=VoiceTurn.State.SYNTHESIZING,
            assistant_message_id=601,
        )

    def execute(self, *, state, recovered=None, real=True, store=True):
        self.turn.state = state

        if recovered is None:
            recovered = SimpleNamespace(
                state=VoiceTurn.State.COMPLETED,
                audio_available=True,
            )

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
                "recover_real_voice_audio",
                return_value=recovered,
            ) as recovery,
            patch.object(
                orchestrator,
                "recover_voice_answer",
                return_value=SimpleNamespace(
                    state=VoiceTurn.State.COMPLETED,
                    audio=b"legacy",
                ),
            ) as legacy,
            patch.object(
                orchestrator,
                "execute_real_voice_bridge",
            ) as bridge,
        ):
            query.return_value.first.return_value = self.turn

            result = orchestrator.continue_voice_turn(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.turn.request_id,
                audio_store=self.store if store else None,
                real_tts_synthesize=(
                    (lambda text: b"unused") if real else None
                ),
            )

            return (
                result,
                recovery.call_count,
                legacy.call_count,
                bridge.call_count,
            )

    def test_01_synthesizing_recovers_real_audio(self):
        result, recovery, legacy, bridge = self.execute(
            state=VoiceTurn.State.SYNTHESIZING
        )
        self.assertEqual(result["state"], VoiceTurn.State.COMPLETED)
        self.assertTrue(result["audio_available"])
        self.assertEqual(recovery, 1)
        self.assertEqual(legacy, 0)
        self.assertEqual(bridge, 0)

    def test_02_missing_audio_stays_synthesizing(self):
        result, recovery, legacy, bridge = self.execute(
            state=VoiceTurn.State.SYNTHESIZING,
            recovered=SimpleNamespace(
                state=VoiceTurn.State.SYNTHESIZING,
                audio_available=False,
            ),
        )
        self.assertEqual(
            result["state"],
            VoiceTurn.State.SYNTHESIZING,
        )
        self.assertFalse(result["audio_available"])
        self.assertEqual(recovery, 1)
        self.assertEqual(bridge, 0)

    def test_03_completed_turn_is_recoverable(self):
        result, recovery, legacy, bridge = self.execute(
            state=VoiceTurn.State.COMPLETED
        )
        self.assertTrue(result["audio_available"])
        self.assertEqual(recovery, 1)
        self.assertEqual(bridge, 0)

    def test_04_uncertain_never_recovers_or_dispatches(self):
        result, recovery, legacy, bridge = self.execute(
            state=VoiceTurn.State.UNCERTAIN
        )
        self.assertEqual(result["state"], VoiceTurn.State.UNCERTAIN)
        self.assertFalse(result["audio_available"])
        self.assertEqual(recovery, 0)
        self.assertEqual(legacy, 0)
        self.assertEqual(bridge, 0)

    def test_05_default_preserves_legacy_recovery(self):
        result, recovery, legacy, bridge = self.execute(
            state=VoiceTurn.State.SYNTHESIZING,
            real=False,
        )
        self.assertEqual(result["audio"], b"legacy")
        self.assertEqual(recovery, 0)
        self.assertEqual(legacy, 1)
        self.assertEqual(bridge, 0)

    def test_06_real_recovery_requires_store(self):
        with self.assertRaises(VoiceConflict):
            self.execute(
                state=VoiceTurn.State.SYNTHESIZING,
                store=False,
            )
