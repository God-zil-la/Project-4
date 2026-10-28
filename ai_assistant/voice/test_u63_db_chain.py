from types import SimpleNamespace
from unittest.mock import patch

from ai_assistant.voice.models import VoiceTurn
from ai_assistant.voice.orchestrator import continue_voice_turn
from ai_assistant.voice.test_u63_step254 import Step254RealDatabaseTests


class U63DatabaseChainTests(Step254RealDatabaseTests):

    def test_answer_saved_dispatches_real_bridge(self):
        self.turn.state = VoiceTurn.State.ANSWER_SAVED
        self.turn.save(update_fields=["state"])

        with patch(
            "ai_assistant.voice.orchestrator.execute_real_voice_bridge",
            return_value=SimpleNamespace(
                state=VoiceTurn.State.COMPLETED,
                audio_available=True,
            ),
        ) as bridge:
            result = continue_voice_turn(
                user=self.user,
                session_id=self.session.public_id,
                request_id=self.request_id,
                audio_store=self.audio_store,
                real_tts_synthesize=lambda text: b"mocked",
            )

        self.assertEqual(result["state"], VoiceTurn.State.COMPLETED)
        self.assertTrue(result["audio_available"])
        self.assertEqual(
            result["assistant_message_id"],
            self.message.pk,
        )
        bridge.assert_called_once()
