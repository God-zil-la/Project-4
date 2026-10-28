"""U6.3 Step 251: isolated integration and recovery tests."""

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from ai_assistant.voice import real_audio_recovery as recovery
from ai_assistant.voice import real_voice_bridge as bridge
from ai_assistant.voice.models import VoiceTurn
from ai_assistant.voice.real_tts_identity import (
    validate_real_tts_identity,
)


class Step251IntegrationTests(TransactionTestCase):

    def setUp(self):
        # Provider unit tests isolate session authorization; Block C tests exercise it in the database.
        guard = patch("ai_assistant.voice.service._session")
        guard.start()
        self.addCleanup(guard.stop)
        self.user = SimpleNamespace(pk=101)
        self.session_id = uuid4()
        self.request_id = uuid4()
        self.conversation_id = uuid4()

        self.session = SimpleNamespace(
            public_id=self.session_id,
            assistant_id=12,
            conversation=SimpleNamespace(
                public_id=self.conversation_id,
            ),
        )

        self.turn = SimpleNamespace(
            state=VoiceTurn.State.SYNTHESIZING,
            request_id=self.request_id,
            assistant_message_id=34,
            session=self.session,
        )

        self.store = Mock()

    def bridge_args(self):
        return dict(
            user=self.user,
            session_id=self.session_id,
            request_id=self.request_id,
            audio_store=self.store,
            synthesize=Mock(),
        )

    def recovery_args(self):
        return dict(
            user=self.user,
            session_id=self.session_id,
            request_id=self.request_id,
            audio_store=self.store,
        )

    def test_01_successful_bridge_finalization(self):
        result = SimpleNamespace(
            state="succeeded",
            request_id=self.request_id,
            audio_available=True,
        )

        with (
            patch.object(
                bridge.voice_service,
                "claim_tts_dispatch",
                return_value=(self.turn, True),
            ),
            patch.object(
                bridge,
                "execute_isolated_live_tts",
                return_value=result,
            ),
            patch.object(
                bridge,
                "recover_real_voice_audio",
                return_value=SimpleNamespace(
                    state=VoiceTurn.State.COMPLETED,
                    request_id=self.request_id,
                    audio_available=True,
                ),
            ) as recover,
        ):
            output = bridge.execute_real_voice_bridge(
                **self.bridge_args()
            )

        self.assertEqual(
            output.state,
            VoiceTurn.State.COMPLETED,
        )
        self.assertTrue(output.audio_available)

        recover.assert_called_once_with(
            user=self.user,
            session_id=self.session_id,
            request_id=self.request_id,
            audio_store=self.store,
        )

    def test_02_duplicate_bridge_never_synthesizes(self):
        self.turn.state = VoiceTurn.State.SYNTHESIZING

        with (
            patch.object(
                bridge.voice_service,
                "claim_tts_dispatch",
                return_value=(self.turn, False),
            ),
            patch.object(
                bridge,
                "execute_isolated_live_tts",
            ) as execute,
        ):
            output = bridge.execute_real_voice_bridge(
                **self.bridge_args()
            )

        self.assertFalse(output.audio_available)
        execute.assert_not_called()

    def test_03_provider_exception_preserves_state(self):
        with (
            patch.object(
                bridge.voice_service,
                "claim_tts_dispatch",
                return_value=(self.turn, True),
            ),
            patch.object(
                bridge,
                "execute_isolated_live_tts",
                side_effect=RuntimeError("provider_failed"),
            ),
            patch.object(
                bridge.voice_service,
                "advance_turn",
            ) as advance,
        ):
            with self.assertRaises(RuntimeError):
                bridge.execute_real_voice_bridge(
                    **self.bridge_args()
                )

        advance.assert_not_called()

    def run_recovery(
        self,
        *,
        tts_row=True,
        audio=b"ID3\x04\x00\x00\x00\x00",
        state=VoiceTurn.State.SYNTHESIZING,
    ):
        self.turn.state = state

        with (
            patch.object(
                recovery.voice_service,
                "_session",
                return_value=self.session,
            ),
            patch.object(
                recovery.voice_service,
                "_uuid",
                return_value=self.request_id,
            ),
            patch.object(
                recovery.VoiceTurn.objects,
                "filter",
            ) as voice_filter,
            patch.object(
                recovery,
                "get_assistant_message",
                return_value="Saved AI answer",
            ),
            patch.object(
                recovery,
                "validate_real_tts_identity",
                return_value=(self.request_id, "fingerprint"),
            ),
            patch.object(
                recovery.TTSRequest.objects,
                "filter",
            ) as tts_filter,
            patch.object(
                recovery,
                "retrieve_audio",
                return_value=audio,
            ) as retrieve,
            patch.object(
                recovery,
                "validate_live_mp3",
                return_value=audio,
            ),
            patch.object(
                recovery.voice_service,
                "advance_turn",
            ) as advance,
        ):
            voice_filter.return_value.first.return_value = self.turn
            tts_filter.return_value.first.return_value = (
                Mock() if tts_row else None
            )

            result = recovery.recover_real_voice_audio(
                **self.recovery_args()
            )

            return result, advance, retrieve

    def test_04_recovery_after_storage(self):
        result, advance, retrieve = self.run_recovery()

        self.assertTrue(result.audio_available)
        self.assertEqual(
            result.state,
            VoiceTurn.State.COMPLETED,
        )
        advance.assert_called_once()
        retrieve.assert_called_once()

    def test_05_missing_tts_record_blocks_recovery(self):
        result, advance, retrieve = self.run_recovery(
            tts_row=False
        )

        self.assertFalse(result.audio_available)
        advance.assert_not_called()
        retrieve.assert_not_called()

    def test_06_missing_audio_blocks_completion(self):
        result, advance, _ = self.run_recovery(
            audio=None
        )

        self.assertFalse(result.audio_available)
        advance.assert_not_called()

    def test_07_completed_turn_is_idempotent(self):
        result, advance, _ = self.run_recovery(
            state=VoiceTurn.State.COMPLETED
        )

        self.assertTrue(result.audio_available)
        advance.assert_not_called()

    def test_08_invalid_state_blocks_recovery(self):
        self.turn.state = VoiceTurn.State.ANSWER_SAVED

        with (
            patch.object(
                recovery.voice_service,
                "_session",
                return_value=self.session,
            ),
            patch.object(
                recovery.voice_service,
                "_uuid",
                return_value=self.request_id,
            ),
            patch.object(
                recovery.VoiceTurn.objects,
                "filter",
            ) as voice_filter,
        ):
            voice_filter.return_value.first.return_value = self.turn

            with self.assertRaises(
                recovery.RealAudioRecoveryError
            ):
                recovery.recover_real_voice_audio(
                    **self.recovery_args()
                )

    def test_09_identity_changes_with_text(self):
        base = dict(
            assistant_id=12,
            conversation_id=self.conversation_id,
            message_id=34,
            request_id=self.request_id,
        )

        _, first = validate_real_tts_identity(
            text="Original answer",
            **base,
        )

        _, second = validate_real_tts_identity(
            text="Changed answer",
            **base,
        )

        self.assertNotEqual(first, second)

    def test_10_identity_changes_with_message(self):
        base = dict(
            text="Saved answer",
            assistant_id=12,
            conversation_id=self.conversation_id,
            request_id=self.request_id,
        )

        _, first = validate_real_tts_identity(
            message_id=34,
            **base,
        )

        _, second = validate_real_tts_identity(
            message_id=35,
            **base,
        )

        self.assertNotEqual(first, second)

    def test_11_missing_store_blocks_bridge(self):
        args = self.bridge_args()
        args["audio_store"] = None

        with patch.object(
            bridge.voice_service,
            "claim_tts_dispatch",
        ) as claim:
            with self.assertRaises(
                bridge.RealVoiceBridgeError
            ):
                bridge.execute_real_voice_bridge(**args)

        claim.assert_not_called()

    def test_12_missing_store_blocks_recovery(self):
        args = self.recovery_args()
        args["audio_store"] = None

        with self.assertRaises(
            recovery.RealAudioRecoveryError
        ):
            recovery.recover_real_voice_audio(**args)


class Step251SourceTests(TransactionTestCase):

    def test_13_voice_python_syntax(self):
        root = Path("ai_assistant/voice")
        files = list(root.rglob("*.py"))

        self.assertGreater(len(files), 0)

        for path in files:
            with self.subTest(path=str(path)):
                ast.parse(
                    path.read_text(encoding="utf-8-sig")
                )

    def test_14_recovery_has_no_provider_import(self):
        source = Path(
            "ai_assistant/voice/real_audio_recovery.py"
        ).read_text(encoding="utf-8-sig")

        self.assertNotIn(
            "provider_openai",
            source,
        )
        self.assertNotIn(
            "synthesize_live_voice_audio",
            source,
        )
