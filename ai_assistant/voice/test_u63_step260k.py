"""U6.3 real ledger-to-trusted-pipeline integration tests.

Uses the test database and mocked external providers.
No production API calls.
"""

from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import TransactionTestCase

from ai_assistant.bots.models import Bot, Conversation
from ai_assistant.stt.models import STTPeriod
from ai_assistant.stt.normalizer import reserve_normalized

from .models import VoiceTurn
from .service import VoiceConflict, reserve_turn, start_session
from .trusted_live_integration import execute_trusted_live_voice
from .test_stt_ledger_integration import VoiceSTTLedgerIntegrationTests


class Step260KTrustedPipelineTests(TransactionTestCase):

    def setUp(self):
        fixture = VoiceSTTLedgerIntegrationTests(
            methodName="test_real_reservation_dispatch_and_settlement"
        )
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)

        self.user = fixture.user
        self.evidence = fixture.evidence

        self.bot = Bot.objects.create(
            owner=self.user,
            name="U6.3 Trusted Integration Test",
        )

        self.conversation = Conversation.objects.create(
            user=self.user,
            bot=self.bot,
        )

        self.session = start_session(
            user=self.user,
            assistant=self.bot,
            conversation=self.conversation,
        )

        self.request_id = uuid4()
        self.audio_hash = "e" * 64

        self.turn, created = reserve_turn(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
            audio_sha256=self.audio_hash,
        )
        self.assertTrue(created)

        self.reservation = reserve_normalized(
            evidence=self.evidence,
            request_id=self.request_id,
            duration_ms=61000,
            audio_sha256=self.audio_hash,
            assistant_id=self.bot.pk,
        )

        self.audio = SimpleNamespace(sha256=self.audio_hash)
        self.transcriber = Mock(return_value="Hej från Live Voice")

    def run_trusted(self):
        return execute_trusted_live_voice(
            user=self.user,
            session_id=self.session.public_id,
            request_id=self.request_id,
            reservation=self.reservation,
            evidence=self.evidence,
            audio=self.audio,
            transcriber=self.transcriber,
        )

    def test_real_reservation_reaches_voice_continuation(self):
        voice_result = {"state": "mocked_voice_complete"}

        with patch(
            "ai_assistant.voice.live_pipeline.continue_voice_turn",
            return_value=voice_result,
        ) as continuation:
            result = self.run_trusted()

        self.assertEqual(
            result["stt_state"],
            VoiceTurn.State.TRANSCRIBED,
        )
        self.assertEqual(
            result["transcript"],
            "Hej från Live Voice",
        )
        self.assertEqual(result["voice"], voice_result)

        self.transcriber.assert_called_once_with(self.audio)
        continuation.assert_called_once()

        self.turn.refresh_from_db()
        self.reservation.refresh_from_db()

        period = STTPeriod.objects.get(
            pk=self.reservation.period_id
        )

        self.assertEqual(
            self.turn.state,
            VoiceTurn.State.TRANSCRIBED,
        )
        self.assertEqual(
            self.reservation.state,
            "consumed",
        )
        self.assertEqual(period.reserved_ms, 0)
        self.assertEqual(period.used_ms, 120000)

        with patch(
            "ai_assistant.voice.live_pipeline.continue_voice_turn"
        ) as continuation_retry:
            with self.assertRaises(VoiceConflict):
                self.run_trusted()

            continuation_retry.assert_not_called()

        self.transcriber.assert_called_once_with(self.audio)

        period.refresh_from_db()
        self.assertEqual(period.used_ms, 120000)

    def test_provider_error_does_not_start_ai(self):
        self.transcriber.side_effect = RuntimeError(
            "Simulated uncertain STT outcome"
        )

        with patch(
            "ai_assistant.voice.live_pipeline.continue_voice_turn"
        ) as continuation:
            with self.assertRaises(RuntimeError):
                self.run_trusted()

            continuation.assert_not_called()

        self.transcriber.assert_called_once_with(self.audio)

        self.reservation.refresh_from_db()
        self.turn.refresh_from_db()

        self.assertEqual(
            self.turn.state,
            VoiceTurn.State.UNCERTAIN,
        )

        with patch(
            "ai_assistant.voice.live_pipeline.continue_voice_turn"
        ) as continuation_retry:
            with self.assertRaises(VoiceConflict):
                self.run_trusted()

            continuation_retry.assert_not_called()

        self.transcriber.assert_called_once_with(self.audio)