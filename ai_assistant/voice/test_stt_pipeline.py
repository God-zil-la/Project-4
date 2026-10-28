"""Isolated regression tests for the U6.3 STT pipeline."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from ai_assistant.stt.normalizer import ServerPeriodEvidence
from ai_assistant.voice.models import VoiceTurn
from ai_assistant.voice.service import VoiceConflict
from ai_assistant.voice.stt_pipeline import execute_testable_stt


class STTPipelineTests(SimpleTestCase):
    def setUp(self):
        # Provider unit tests isolate session authorization; Block C tests exercise it in the database.
        guard = patch("ai_assistant.voice.service._session")
        guard.start()
        self.addCleanup(guard.stop)
        self.user = SimpleNamespace(pk=101)
        self.session = SimpleNamespace(
            public_id="test-session",
        )
        self.turn = SimpleNamespace(
            request_id="test-request",
        )
        self.reservation = SimpleNamespace(pk=202)
        self.audio = object()

        # This is a type-only fixture. All entitlement and
        # reservation operations are mocked in these unit tests.
        self.evidence = object.__new__(ServerPeriodEvidence)

    def execute(self, transcriber):
        return execute_testable_stt(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.turn.request_id,
            reservation=self.reservation,
            evidence=self.evidence,
            audio=self.audio,
            transcriber=transcriber,
        )

    def test_successful_transcription_settles_and_saves(self):
        with (
            patch(
                "ai_assistant.voice.stt_pipeline.prepare_reserved_stt",
                return_value=(self.session, self.turn),
            ),
            patch(
                "ai_assistant.voice.stt_pipeline.claim_voice_stt",
                return_value=True,
            ),
            patch(
                "ai_assistant.voice.stt_pipeline.advance_turn",
            ) as advance,
            patch(
                "ai_assistant.voice.stt_pipeline.ledger.settle",
            ) as settle,
            patch(
                "ai_assistant.voice.stt_pipeline.accept_stt_result",
            ) as accept,
            patch(
                "ai_assistant.voice.stt_pipeline.transaction.atomic",
            ),
        ):
            result = self.execute(lambda audio: " Hello from STT ")

        self.assertEqual(result.state, VoiceTurn.State.TRANSCRIBED)
        self.assertEqual(result.transcript, "Hello from STT")
        settle.assert_called_once_with(
            user_id=101,
            reservation_id=202,
            outcome="success",
        )
        accept.assert_called_once()
        self.assertEqual(advance.call_count, 1)

    def test_provider_error_retains_uncertain_reservation(self):
        transcriber = Mock(side_effect=RuntimeError("Provider timeout"))

        with (
            patch(
                "ai_assistant.voice.stt_pipeline.prepare_reserved_stt",
                return_value=(self.session, self.turn),
            ),
            patch(
                "ai_assistant.voice.stt_pipeline.claim_voice_stt",
                return_value=True,
            ),
            patch(
                "ai_assistant.voice.stt_pipeline.advance_turn",
            ) as advance,
            patch(
                "ai_assistant.voice.stt_pipeline.ledger.settle",
            ) as settle,
            patch(
                "ai_assistant.voice.stt_pipeline.transaction.atomic",
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "Provider timeout"):
                self.execute(transcriber)

        transcriber.assert_called_once_with(self.audio)
        settle.assert_called_once_with(
            user_id=101,
            reservation_id=202,
            outcome="uncertain",
        )
        self.assertEqual(advance.call_count, 2)

    def test_duplicate_dispatch_never_calls_provider(self):
        transcriber = Mock(return_value="Should never run")

        with (
            patch(
                "ai_assistant.voice.stt_pipeline.prepare_reserved_stt",
                return_value=(self.session, self.turn),
            ),
            patch(
                "ai_assistant.voice.stt_pipeline.claim_voice_stt",
                return_value=False,
            ),
            patch(
                "ai_assistant.voice.stt_pipeline.advance_turn",
            ) as advance,
            patch(
                "ai_assistant.voice.stt_pipeline.ledger.settle",
            ) as settle,
            patch(
                "ai_assistant.voice.stt_pipeline.transaction.atomic",
            ),
        ):
            with self.assertRaisesRegex(
                VoiceConflict,
                "STT already dispatched",
            ):
                self.execute(transcriber)

        transcriber.assert_not_called()
        advance.assert_not_called()
        settle.assert_not_called()
