from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import TransactionTestCase

from ai_assistant.bots.models import Bot, Conversation
from ai_assistant.stt.models import STTPeriod
from ai_assistant.stt.normalizer import reserve_normalized
from ai_assistant.voice.models import VoiceTurn
from ai_assistant.voice.service import (
    VoiceConflict,
    reserve_turn,
    start_session,
)
from ai_assistant.voice.stt_pipeline import execute_testable_stt
from ai_assistant.voice.test_stt_ledger_integration import (
    VoiceSTTLedgerIntegrationTests,
)


class VoiceSTTFullIntegrationTests(TransactionTestCase):

    def test_dispatch_survives_turn_transition_failure(self):
        fixture = VoiceSTTLedgerIntegrationTests(
            methodName="test_real_reservation_dispatch_and_settlement"
        )
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)

        user = fixture.user
        evidence = fixture.evidence

        bot = Bot.objects.create(
            owner=user,
            name="U6.3 Dispatch Crash Test",
        )
        conversation = Conversation.objects.create(
            user=user,
            bot=bot,
        )
        session = start_session(
            user=user,
            assistant=bot,
            conversation=conversation,
        )

        request_id = uuid4()
        audio_hash = "d" * 64

        turn, _ = reserve_turn(
            user=user,
            session_id=session.public_id,
            request_id=request_id,
            audio_sha256=audio_hash,
        )

        reservation = reserve_normalized(
            evidence=evidence,
            request_id=request_id,
            duration_ms=61000,
            audio_sha256=audio_hash,
            assistant_id=bot.pk,
        )

        audio = SimpleNamespace(sha256=audio_hash)
        transcriber = Mock(return_value="Ska aldrig k?ras")

        with patch(
            "ai_assistant.voice.stt_pipeline.advance_turn",
            side_effect=RuntimeError("Simulated crash after dispatch"),
        ):
            with self.assertRaisesRegex(
                RuntimeError, "Simulated crash after dispatch"
            ):
                execute_testable_stt(
                    user=user,
                    session_id=session.public_id,
                    request_id=request_id,
                    reservation=reservation,
                    evidence=evidence,
                    audio=audio,
                    transcriber=transcriber,
                )

        reservation.refresh_from_db()
        turn.refresh_from_db()
        period = STTPeriod.objects.get(pk=reservation.period_id)

        self.assertEqual(reservation.state, "dispatched")
        self.assertEqual(turn.state, VoiceTurn.State.CREATED)
        self.assertEqual(period.reserved_ms, 120000)
        self.assertEqual(period.used_ms, 0)
        transcriber.assert_not_called()

        with self.assertRaises(VoiceConflict):
            execute_testable_stt(
                user=user,
                session_id=session.public_id,
                request_id=request_id,
                reservation=reservation,
                evidence=evidence,
                audio=audio,
                transcriber=transcriber,
            )

        transcriber.assert_not_called()

        reservation.refresh_from_db()
        period.refresh_from_db()
        self.assertEqual(reservation.state, "dispatched")
        self.assertEqual(period.reserved_ms, 120000)
        self.assertEqual(period.used_ms, 0)

    def test_real_voice_turn_transcription(self):
        # Reuse only the known-good fixture setup, not inherited tests.
        fixture = VoiceSTTLedgerIntegrationTests(
            methodName="test_real_reservation_dispatch_and_settlement"
        )
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)

        user = fixture.user
        evidence = fixture.evidence

        bot = Bot.objects.create(
            owner=user,
            name="U6.3 Real Turn Test",
        )
        conversation = Conversation.objects.create(
            user=user,
            bot=bot,
        )
        session = start_session(
            user=user,
            assistant=bot,
            conversation=conversation,
        )

        request_id = uuid4()
        audio_hash = "c" * 64

        turn, _ = reserve_turn(
            user=user,
            session_id=session.public_id,
            request_id=request_id,
            audio_sha256=audio_hash,
        )
        self.assertEqual(turn.state, VoiceTurn.State.CREATED)

        reservation = reserve_normalized(
            evidence=evidence,
            request_id=request_id,
            duration_ms=61000,
            audio_sha256=audio_hash,
            assistant_id=bot.pk,
        )

        audio = SimpleNamespace(sha256=audio_hash)
        transcriber = Mock(return_value="Hej fr?n riktig integration")

        result = execute_testable_stt(
            user=user,
            session_id=session.public_id,
            request_id=request_id,
            reservation=reservation,
            evidence=evidence,
            audio=audio,
            transcriber=transcriber,
        )

        turn.refresh_from_db()
        reservation.refresh_from_db()
        period = STTPeriod.objects.get(pk=reservation.period_id)

        self.assertEqual(result.state, VoiceTurn.State.TRANSCRIBED)
        self.assertEqual(
            result.transcript,
            "Hej fr?n riktig integration",
        )
        self.assertEqual(turn.state, VoiceTurn.State.TRANSCRIBED)
        self.assertEqual(
            turn.transcript,
            "Hej fr?n riktig integration",
        )
        self.assertEqual(reservation.state, "consumed")
        self.assertEqual(period.reserved_ms, 0)
        self.assertEqual(period.used_ms, 120000)
        transcriber.assert_called_once_with(audio)

        with self.assertRaises(VoiceConflict):
            execute_testable_stt(
                user=user,
                session_id=session.public_id,
                request_id=request_id,
                reservation=reservation,
                evidence=evidence,
                audio=audio,
                transcriber=transcriber,
            )

        transcriber.assert_called_once_with(audio)
        period.refresh_from_db()
        self.assertEqual(period.used_ms, 120000)
        self.assertEqual(period.reserved_ms, 0)
